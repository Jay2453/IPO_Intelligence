from sqlalchemy import Column, String, Integer, Float, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid


class FinancialObservation(Base, TimestampedModel):
    __tablename__ = "financial_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ipo_id = Column(String(36), ForeignKey("ipos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    fiscal_year = Column(String(20), nullable=False)  # e.g., FY22, FY23, FY24, H1FY25, 9MFY24
    period_months = Column(Integer, nullable=False, default=12)
    
    revenue_crores = Column(Float, nullable=True)
    ebitda_crores = Column(Float, nullable=True)
    pat_crores = Column(Float, nullable=True)
    total_assets_crores = Column(Float, nullable=True)
    net_worth_crores = Column(Float, nullable=True)
    total_liabilities_crores = Column(Float, nullable=True)
    total_debt_crores = Column(Float, nullable=True)
    operating_cash_flow_crores = Column(Float, nullable=True)
    
    roe_pct = Column(Float, nullable=True)
    roce_pct = Column(Float, nullable=True)
    eps_inr = Column(Float, nullable=True)
    nav_per_share_inr = Column(Float, nullable=True)
    
    source_document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    source_page = Column(Integer, nullable=True)
    statement_type = Column(String(30), nullable=False, default="CONSOLIDATED")  # CONSOLIDATED, STANDALONE
    is_restated = Column(Boolean, nullable=False, default=True)
    currency = Column(String(10), nullable=False, default="INR")
    unit = Column(String(20), nullable=False, default="CRORES")
    extraction_method = Column(String(50), nullable=False, default="PDFPLUMBER_TABLE")  # PDFPLUMBER_TABLE, OCR_FALLBACK, MANUAL_OVERRIDE
    verification_status = Column(String(30), nullable=False, default="EXTRACTED")  # EXTRACTED, VERIFIED, CONFLICT, UNVERIFIED
    raw_data_provenance = Column(JSON, nullable=True)

    ipo = relationship("IPO", back_populates="financials")
    source_document = relationship("Document", back_populates="financials")

