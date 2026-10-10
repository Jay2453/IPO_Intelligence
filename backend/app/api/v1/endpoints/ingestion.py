import math
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc
from app.core.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.ingestion import IngestionJobResponse
from app.models.ingestion import IngestionJob

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
