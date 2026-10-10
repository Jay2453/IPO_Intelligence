from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_v1_router
from app.core.database import engine
from app.models import Base


import asyncio
import logging

logger = logging.getLogger("ipo_intelligence")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist on startup if running in development mode
    if settings.ENVIRONMENT != "production":
        Base.metadata.create_all(bind=engine)

    # Optional background scheduled ingestion worker (default 15 minutes)
    worker_task = None
    if settings.ENABLE_SCHEDULED_INGESTION:
        from app.core.database import SessionLocal
        from app.services.ingestion_service import IngestionService

        async def scheduled_sync_worker():
            interval_seconds = max(60, settings.INGESTION_SYNC_INTERVAL_MINUTES * 60)
            logger.info(f"Starting scheduled ingestion worker (interval: {interval_seconds}s)")
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    db = SessionLocal()
                    try:
                        service = IngestionService()
                        result = service.sync_nse_ipos(db=db, include_recent_past=True, past_limit=30)
                        logger.info(f"Scheduled sync completed: {result['total_processed']} records processed")
                    finally:
                        db.close()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Scheduled ingestion error: {e}")

        worker_task = asyncio.create_task(scheduled_sync_worker())

    yield

    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="IPO Intelligence API",
    description=(
        "Institutional-grade financial intelligence and predictive pipeline for Indian IPOs. "
        "Strictly distinguishes verified regulatory data from demonstration records."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 Router
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/", tags=["Root"])
def root_status():
    return {
        "service": "IPO Intelligence API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "api_v1": "/api/v1",
    }
