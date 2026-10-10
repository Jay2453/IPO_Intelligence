"""
SEBI public filings and document ingestion API endpoints.
GET  /api/v1/sebi/status            — SEBI integration health & document stats
POST /api/v1/sebi/sync              — Trigger SEBI discovery + document sync
GET  /api/v1/sebi/verify-connection — Verify live SEBI portal connectivity

GET  /api/v1/documents              — List all stored documents
GET  /api/v1/documents/{id}         — Get single document with provenance
POST /api/v1/documents/{id}/extract — Re-trigger extraction on a stored document

GET  /api/v1/ipos/{ipo_id}/documents  — List documents for an IPO
GET  /api/v1/ipos/{ipo_id}/financials — List financial observations with provenance
"""
import math
import io
from typing import Optional
from fastapi import APIRouter, Depends, Query, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from app.core.config import settings
from app.core.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.documents import DocumentResponse
from app.schemas.financials import FinancialObservationResponse
from app.models.documents import Document
from app.models.financials import FinancialObservation
from app.services.document_service import DocumentService
from app.pipeline.sebi_adapter import SebiPublicIssuesAdapter
from app.pipeline.pdf_extractor import PdfFinancialExtractor

router = APIRouter()


def _require_api_key(x_api_key: Optional[str]) -> None:
    """Raises 403 if INGESTION_API_KEY is set and key doesn't match."""
    if settings.INGESTION_API_KEY:
        if not x_api_key or x_api_key != settings.INGESTION_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing ingestion authorization key.",
            )


# ─── SEBI Health & Sync ────────────────────────────────────────────────────────

@router.get("/sebi/verify-connection", tags=["SEBI"])
def verify_sebi_connection():
    """
    Verifies live connectivity to the official SEBI public issues portal.
    Does not mutate any data.
    """
    adapter = SebiPublicIssuesAdapter()
    return adapter.verify_connection()


@router.get("/sebi/status", tags=["SEBI"])
def sebi_integration_status(db: Session = Depends(get_db)):
    """
    Returns SEBI integration health and a summary of stored document/extraction stats.
    """
    adapter = SebiPublicIssuesAdapter()
    connection_status = adapter.verify_connection()

    service = DocumentService(adapter=adapter)
    doc_stats = service.get_document_status(db)

    return {
        "connection": connection_status,
        "document_stats": doc_stats,
    }


@router.post("/sebi/sync", tags=["SEBI"])
def trigger_sebi_sync(
    max_documents: int = Query(
        settings.SEBI_MAX_DOCUMENTS_PER_SYNC,
        ge=1,
        le=50,
        description="Maximum number of new documents to discover and process",
    ),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Triggers a manual SEBI public issue discovery and document synchronization.
    Downloads PDFs, extracts financials, and stores provenance.
    """
    _require_api_key(x_api_key)

    service = DocumentService()
    try:
        result = service.sync_sebi_documents(db=db, max_documents=max_documents)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SEBI sync failed: {str(exc)}",
        )


# ─── Document Endpoints ────────────────────────────────────────────────────────

@router.get("/documents", response_model=PaginatedResponse[DocumentResponse], tags=["Documents"])
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    extraction_status: Optional[str] = Query(None, description="PENDING, EXTRACTED, FAILED, UNMATCHED"),
    document_type: Optional[str] = Query(None, description="DRHP, RHP, DRAFT_ABRIDGED_PROSPECTUS, etc."),
    db: Session = Depends(get_db),
):
    """Lists all stored documents with optional filtering."""
    stmt = select(Document)
    if extraction_status:
        stmt = stmt.where(Document.extraction_status == extraction_status)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    stmt = stmt.order_by(desc(Document.created_at)).offset(offset).limit(page_size)
    items = db.scalars(stmt).all()
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse, tags=["Documents"])
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Returns a single document by ID with full provenance metadata."""
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.post("/documents/{document_id}/extract", tags=["Documents"])
def reprocess_document_extraction(
    document_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Re-triggers financial extraction on a stored document.
    Useful if the PDF extractor has been improved since initial ingestion.
    """
    _require_api_key(x_api_key)

    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not doc.ipo_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document is not associated with an IPO and cannot be extracted automatically.",
        )

    from app.models.ipo import IPO
    ipo = db.get(IPO, doc.ipo_id)
    if not ipo:
        raise HTTPException(status_code=404, detail="Associated IPO not found.")

    # Re-download the document
    adapter = SebiPublicIssuesAdapter()
    try:
        doc_data = adapter.fetch_document(doc.file_url)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not re-download document: {exc}",
        )

    # Validate hash integrity
    if doc_data["file_hash_sha256"] != doc.file_hash_sha256:
        # Document has changed server-side — update hash and flag
        doc.file_hash_sha256 = doc_data["file_hash_sha256"]
        doc.extraction_status = "PENDING"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document hash changed since last download. Record updated; please re-trigger extraction.",
        )

    service = DocumentService(adapter=adapter)
    try:
        count = service._extract_and_store_financials(
            db=db,
            document=doc,
            ipo=ipo,
            pdf_bytes=doc_data["payload"],
        )
        db.commit()
        return {
            "document_id": document_id,
            "financial_periods_extracted": count,
            "extraction_status": doc.extraction_status,
        }
    except Exception as exc:
        doc.extraction_status = "FAILED"
        doc.extraction_error = str(exc)[:1000]
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {exc}",
        )


# ─── IPO-scoped Document & Financial Endpoints ────────────────────────────────

@router.get("/ipos/{ipo_id}/documents", response_model=PaginatedResponse[DocumentResponse], tags=["Documents"])
def list_ipo_documents(
    ipo_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Lists all SEBI documents associated with a specific IPO."""
    from app.models.ipo import IPO
    ipo = db.get(IPO, ipo_id)
    if not ipo:
        raise HTTPException(status_code=404, detail="IPO not found.")

    stmt = select(Document).where(Document.ipo_id == ipo_id).order_by(desc(Document.filing_date))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    items = db.scalars(stmt).all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/ipos/{ipo_id}/financials", response_model=PaginatedResponse[FinancialObservationResponse], tags=["Financials"])
def list_ipo_financials(
    ipo_id: str,
    statement_type: Optional[str] = Query(None, description="CONSOLIDATED or STANDALONE"),
    db: Session = Depends(get_db),
):
    """
    Lists financial observations for an IPO with full source provenance.
    Includes source document ID, page number, extraction method, and validation status.
    """
    from app.models.ipo import IPO
    ipo = db.get(IPO, ipo_id)
    if not ipo:
        raise HTTPException(status_code=404, detail="IPO not found.")

    stmt = select(FinancialObservation).where(FinancialObservation.ipo_id == ipo_id)
    if statement_type:
        stmt = stmt.where(FinancialObservation.statement_type == statement_type)

    stmt = stmt.order_by(desc(FinancialObservation.fiscal_year))
    items = db.scalars(stmt).all()

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=1,
        page_size=len(items) or 1,
        total_pages=1,
    )
