from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid, utcnow


class SourceObservation(Base, TimestampedModel):
    __tablename__ = "source_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ipo_id = Column(String(36), ForeignKey("ipos.id", ondelete="CASCADE"), nullable=True, index=True)
    
    source_name = Column(String(100), nullable=False)  # SEBI_PUBLIC_FILINGS, NSE_CIRCULAR, BSE_NOTICE
    canonical_url = Column(Text, nullable=False)
    content_hash_sha256 = Column(String(64), nullable=False, index=True)
    publication_timestamp = Column(DateTime(timezone=True), nullable=True)
    retrieval_timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    validation_status = Column(String(30), nullable=False, default="VALID")  # VALID, UNVERIFIED, HASH_MISMATCH, REJECTED
    raw_metadata = Column(JSON, nullable=True)

    ipo = relationship("IPO", back_populates="sources")
