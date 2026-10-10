from sqlalchemy import Column, String, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid


class FinancialObservation(Base, TimestampedModel):
    __tablename__ = "financial_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ipo_id = Column(String(36), ForeignKey("ipos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    fiscal_year = Column(String(20), nullable=False)  # e.g., FY22, FY23, FY24, H1FY25
    period_months = Column(Integer, nullable=False, default=12)
    
    revenue_crores = Column(Float, nullable=True)
    ebitda_crores = Column(Float, nullable=True)
    pat_crores = Column(Float, nullable=True)
    total_assets_crores = Column(Float, nullable=True)
    net_worth_crores = Column(Float, nullable=True)
    total_debt_crores = Column(Float, nullable=True)
    
    roe_pct = Column(Float, nullable=True)
    roce_pct = Column(Float, nullable=True)
    eps_inr = Column(Float, nullable=True)
    nav_per_share_inr = Column(Float, nullable=True)
    
    source_document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)

    ipo = relationship("IPO", back_populates="financials")
    source_document = relationship("Document")
