import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc
from app.core.config import settings
from app.core.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.ingestion import IngestionJobResponse
from app.models.ingestion import IngestionJob
from app.services.ingestion_service import IngestionService
from app.pipeline.nse_adapter import NseIpoSourceAdapter

router = APIRouter()


@router.get("/ingestion/jobs", response_model=PaginatedResponse[IngestionJobResponse], tags=["Ingestion"])
def list_ingestion_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by RUNNING, SUCCESS, PARTIAL, FAILED"),
    db: Session = Depends(get_db),
):
    """
    Audit log of automated document synchronization, discovery, and reconciliation jobs.
    """
    stmt = select(IngestionJob)
    if status and status != "ALL":
        stmt = stmt.where(IngestionJob.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    stmt = stmt.order_by(desc(IngestionJob.started_at)).offset(offset).limit(page_size)
    items = db.scalars(stmt).all()
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/ingestion/sync", tags=["Ingestion"])
def trigger_manual_sync(
    include_past: bool = Query(True, description="Whether to include recent past issues"),
    past_limit: int = Query(30, ge=1, le=100, description="Max recent past issues to sync"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", description="API key if required"),
    db: Session = Depends(get_db),
):
    """
    Triggers a manual synchronization against the official NSE IPO information portal.
    Deduplicates records, preserves source observation hashes, and logs audit records.
    """
    if settings.INGESTION_API_KEY:
        if not x_api_key or x_api_key != settings.INGESTION_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing ingestion authorization key.",
            )

    try:
        service = IngestionService()
        result = service.sync_nse_ipos(
            db=db,
            include_recent_past=include_past,
            past_limit=past_limit,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Synchronization failed: {str(e)}",
        )


@router.get("/ingestion/verify-connection", tags=["Ingestion"])
def verify_source_connection():
    """
    Verifies live connectivity to official NSE IPO endpoints without mutating data.
    """
    adapter = NseIpoSourceAdapter()
    return adapter.verify_live_connection()
