from sqlalchemy import Column, String, Integer, Float, Boolean, Date, Text, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid


class IPO(Base, TimestampedModel):
    __tablename__ = "ipos"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    isin = Column(String(12), nullable=True, index=True)
    bse_scrip_code = Column(String(20), nullable=True, index=True)
    symbol = Column(String(20), nullable=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    exchange = Column(String(20), nullable=False, default="NSE_BSE")  # NSE, BSE, NSE_BSE
    category = Column(String(20), nullable=False, default="MAINBOARD")  # MAINBOARD, SME
    lifecycle_status = Column(String(30), nullable=False, default="DISCOVERED", index=True)
    
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    lot_size = Column(Integer, nullable=True)
    issue_size_crores = Column(Float, nullable=True)
    fresh_issue_crores = Column(Float, nullable=True)
    ofs_crores = Column(Float, nullable=True)
    
    open_date = Column(Date, nullable=True, index=True)
    close_date = Column(Date, nullable=True, index=True)
    allotment_date = Column(Date, nullable=True)
    refund_date = Column(Date, nullable=True)
    credit_date = Column(Date, nullable=True)
    listing_date = Column(Date, nullable=True, index=True)
    
    face_value = Column(Float, nullable=True)
    lead_managers = Column(Text, nullable=True)
    registrar = Column(String(255), nullable=True)
    
    data_completeness_pct = Column(Integer, nullable=False, default=0)
    analysis_status = Column(String(30), nullable=False, default="PENDING", index=True)  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    is_demo = Column(Boolean, nullable=False, default=False, index=True)

    # Relationships
    events = relationship("IPOEvent", back_populates="ipo", cascade="all, delete-orphan", order_by="desc(IPOEvent.event_timestamp)")
    sources = relationship("SourceObservation", back_populates="ipo", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="ipo", cascade="all, delete-orphan")
    financials = relationship("FinancialObservation", back_populates="ipo", cascade="all, delete-orphan", order_by="desc(FinancialObservation.fiscal_year)")
    subscriptions = relationship("SubscriptionSnapshot", back_populates="ipo", cascade="all, delete-orphan", order_by="desc(SubscriptionSnapshot.snapshot_time)")
    market_observations = relationship("MarketObservation", back_populates="ipo", cascade="all, delete-orphan", order_by="desc(MarketObservation.observation_time)")
    predictions = relationship("Prediction", back_populates="ipo", cascade="all, delete-orphan", order_by="desc(Prediction.prediction_timestamp)")

    __table_args__ = (
        Index("ix_ipos_category_status", "category", "lifecycle_status"),
        Index("ix_ipos_dates", "open_date", "close_date", "listing_date"),
    )
