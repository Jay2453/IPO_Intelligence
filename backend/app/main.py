from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_v1_router
from app.core.database import engine
from app.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist on startup if running in development mode
    if settings.ENVIRONMENT != "production":
        Base.metadata.create_all(bind=engine)
    yield


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
