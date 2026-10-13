from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid, utcnow


class MarketObservation(Base, TimestampedModel):
    __tablename__ = "market_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ipo_id = Column(String(36), ForeignKey("ipos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    observation_type = Column(String(30), nullable=False)  # GMP_OBSERVATION, LISTING_OUTCOME
    observation_time = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    
    # Sentiment (GMP)
    gmp_inr = Column(Float, nullable=True)
    gmp_percent = Column(Float, nullable=True)
    
    # Verified Listing Outcomes
    final_issue_price_inr = Column(Float, nullable=True)
    listing_open_price_inr = Column(Float, nullable=True)
    listing_close_price_inr = Column(Float, nullable=True)
    listing_gain_pct = Column(Float, nullable=True)
    bhavcopy_verified = Column(Boolean, nullable=False, default=False)

    # Source Provenance
    exchange = Column(String(20), nullable=True)  # NSE, BSE
    source_url = Column(Text, nullable=True)
    source_file_hash = Column(String(64), nullable=True)
    raw_data_provenance = Column(JSON, nullable=True)

    ipo = relationship("IPO", back_populates="market_observations")
