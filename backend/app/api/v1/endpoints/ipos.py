import math
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.ipo import IPOSummaryResponse, IPODetailResponse
from app.schemas.events import IPOEventResponse
from app.schemas.documents import DocumentResponse
from app.schemas.predictions import PredictionResponse
from app.services.ipo_service import get_ipos_query, get_ipo_by_id
from app.models.events import IPOEvent
from app.models.documents import Document
from app.models.predictions import Prediction

router = APIRouter()


@router.get("/ipos", response_model=PaginatedResponse[IPOSummaryResponse], tags=["IPOs"])
def list_ipos(
    exchange: Optional[str] = Query(None, description="Filter by exchange (NSE, BSE, NSE_BSE, ALL)"),
    category: Optional[str] = Query(None, description="Filter by category (MAINBOARD, SME, ALL)"),
    lifecycle_status: Optional[str] = Query(None, description="Filter by status (DISCOVERED, SUBSCRIPTION_OPEN, etc.)"),
    analysis_status: Optional[str] = Query(None, description="Filter by analysis status (PENDING, COMPLETED, etc.)"),
    search: Optional[str] = Query(None, description="Search company name or symbol"),
    sort_by: str = Query("created_at", description="Field to sort by (created_at, open_date, issue_size_crores, etc.)"),
    sort_order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
):
    """
    Search, filter, and paginate tracked Indian IPOs.
    """
    items, total = get_ipos_query(
        db=db,
        exchange=exchange,
        category=category,
        lifecycle_status=lifecycle_status,
        analysis_status=analysis_status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/ipos/{ipo_id}", response_model=IPODetailResponse, tags=["IPOs"])
def get_ipo_detail(ipo_id: str, db: Session = Depends(get_db)):
    """
    Retrieve comprehensive details for an IPO, including financials, documents, events, and predictions.
    """
    ipo = get_ipo_by_id(db, ipo_id)
    if not ipo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IPO with ID '{ipo_id}' not found.",
        )
    return ipo


@router.get("/ipos/{ipo_id}/events", response_model=List[IPOEventResponse], tags=["IPOs"])
def get_ipo_events(ipo_id: str, db: Session = Depends(get_db)):
    """
    Retrieve chronological timeline and regulatory milestones for an IPO.
    """
    ipo = get_ipo_by_id(db, ipo_id)
    if not ipo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IPO with ID '{ipo_id}' not found.",
        )
    events = db.scalars(
        select(IPOEvent)
        .where(IPOEvent.ipo_id == ipo_id)
        .order_by(IPOEvent.event_timestamp.desc())
    ).all()
    return events


@router.get("/ipos/{ipo_id}/documents", response_model=List[DocumentResponse], tags=["IPOs"])
def get_ipo_documents(ipo_id: str, db: Session = Depends(get_db)):
    """
    Retrieve versioned filing documents (DRHP, RHP, Corrigenda) with cryptographic hashes.
    """
    ipo = get_ipo_by_id(db, ipo_id)
    if not ipo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IPO with ID '{ipo_id}' not found.",
        )
    documents = db.scalars(
        select(Document)
        .where(Document.ipo_id == ipo_id)
        .order_by(Document.created_at.desc())
    ).all()
    return documents


@router.get("/ipos/{ipo_id}/predictions", response_model=List[PredictionResponse], tags=["IPOs"])
def get_ipo_predictions(ipo_id: str, db: Session = Depends(get_db)):
    """
    Retrieve immutable historical model assessments and forecasts for an IPO.
    """
    ipo = get_ipo_by_id(db, ipo_id)
    if not ipo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IPO with ID '{ipo_id}' not found.",
        )
    predictions = db.scalars(
        select(Prediction)
        .where(Prediction.ipo_id == ipo_id)
        .order_by(Prediction.prediction_timestamp.desc())
    ).all()
    return predictions
