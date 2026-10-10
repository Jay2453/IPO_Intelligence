from sqlalchemy import Column, String, Integer, DateTime, Text
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid, utcnow


class IngestionJob(Base, TimestampedModel):
    __tablename__ = "ingestion_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_type = Column(String(50), nullable=False)  # DISCOVERY_POLL, DOCUMENT_SYNC, BHAVCOPY_VERIFICATION
    source_system = Column(String(100), nullable=False)  # SEBI_PORTAL, NSE_FEED, BSE_FEED
    status = Column(String(30), nullable=False, default="RUNNING")  # RUNNING, SUCCESS, PARTIAL, FAILED
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    records_processed = Column(Integer, nullable=False, default=0)
    error_details = Column(Text, nullable=True)
