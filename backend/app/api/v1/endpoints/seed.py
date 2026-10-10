from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.services.seed_service import seed_demo_dataset

router = APIRouter()


@router.post("/seed/demo", tags=["Development Utilities"])
def seed_demo_data(
    force: bool = Query(False, description="Reset existing demo records if true"),
    db: Session = Depends(get_db),
):
    """
    Safely seeds realistic demonstration IPO records with explicit is_demo=True demarcations.
    This endpoint is strictly disabled in production environments and requires ENABLE_DEV_SEED=true.
    """
    if settings.ENVIRONMENT.lower() == "production" or not settings.ENABLE_DEV_SEED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development seeding endpoint is strictly disabled in production environments.",
        )

    result = seed_demo_dataset(db=db, force=force)
    return result
