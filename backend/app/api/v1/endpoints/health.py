from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.system import HealthCheckResponse
from app.services.health_service import get_health_status

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse, tags=["System Health"])
def health_check(db: Session = Depends(get_db)):
    """
    Returns actual application health and verifies live relational database connectivity.
    """
    return get_health_status(db)
