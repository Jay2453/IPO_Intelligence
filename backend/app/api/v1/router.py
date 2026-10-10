from fastapi import APIRouter
from app.api.v1.endpoints import health, ipos, ingestion, system, seed, sebi

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(ipos.router)
api_v1_router.include_router(ingestion.router)
api_v1_router.include_router(system.router)
api_v1_router.include_router(seed.router)
api_v1_router.include_router(sebi.router)

