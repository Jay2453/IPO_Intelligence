from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid, utcnow


class Prediction(Base, TimestampedModel):
    __tablename__ = "predictions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ipo_id = Column(String(36), ForeignKey("ipos.id", ondelete="CASCADE"), nullable=False, index=True)
    model_version_id = Column(String(36), ForeignKey("model_versions.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    prediction_timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    forecast_horizon = Column(String(50), nullable=False, default="LISTING_DAY_CLOSE")  # LISTING_OPEN, LISTING_DAY_CLOSE
    positive_return_prob = Column(Float, nullable=True)  # Calibrated probability 0.0 - 1.0
    predicted_return_pct = Column(Float, nullable=True)  # Expected gain %
    risk_decile = Column(Integer, nullable=True)  # 1 (lowest risk) to 10 (highest risk)
    
    feature_snapshot = Column(JSON, nullable=True)
    evidence_summary = Column(JSON, nullable=True)
    prediction_status = Column(String(30), nullable=False, default="ACTIVE")  # ACTIVE, SUPERSEDED, RETIRED

    ipo = relationship("IPO", back_populates="predictions")
    model_version = relationship("ModelVersion", back_populates="predictions")

    __table_args__ = (
        Index("ix_predictions_ipo_horizon", "ipo_id", "forecast_horizon"),
    )
