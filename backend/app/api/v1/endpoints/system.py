from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.system import SystemStatusResponse
from app.services.health_service import get_system_status

router = APIRouter()


@router.get("/system/status", response_model=SystemStatusResponse, tags=["System Health"])
def system_status(db: Session = Depends(get_db)):
    """
    Returns granular health indicators, source integration status, and synchronization metrics.
    """
    return get_system_status(db)
