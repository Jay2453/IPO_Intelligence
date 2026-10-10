from sqlalchemy import Column, String, Integer, BigInteger, Boolean, Date, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid, utcnow


class Document(Base, TimestampedModel):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ipo_id = Column(String(36), ForeignKey("ipos.id", ondelete="CASCADE"), nullable=True, index=True)
    
    document_type = Column(String(50), nullable=False)  # DRHP, RHP, PROSPECTUS, DRAFT_ABRIDGED_PROSPECTUS, CORRIGENDUM
    issuer_name = Column(String(255), nullable=True, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    file_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    source_url = Column(Text, nullable=True)
    file_hash_sha256 = Column(String(64), nullable=False, index=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    filing_date = Column(Date, nullable=True)
    retrieval_timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    is_current = Column(Boolean, nullable=False, default=True)
    extraction_status = Column(String(50), nullable=False, default="PENDING", index=True)  # PENDING, EXTRACTED, FAILED, UNMATCHED, REVIEW_REQUIRED
    extraction_error = Column(Text, nullable=True)
    extracted_metadata = Column(JSON, nullable=True)

    ipo = relationship("IPO", back_populates="documents")
    financials = relationship("FinancialObservation", back_populates="source_document")

