from sqlalchemy import Column, String, Integer, BigInteger, Boolean, Date, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid


class Document(Base, TimestampedModel):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ipo_id = Column(String(36), ForeignKey("ipos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    document_type = Column(String(50), nullable=False)  # DRHP, RHP, PROSPECTUS, CORRIGENDUM, BASIS_OF_ALLOTMENT
    version_number = Column(Integer, nullable=False, default=1)
    file_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    file_hash_sha256 = Column(String(64), nullable=False, index=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    filing_date = Column(Date, nullable=True)
    is_current = Column(Boolean, nullable=False, default=True)

    ipo = relationship("IPO", back_populates="documents")
