from sqlalchemy import Column, String, Float, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid, utcnow


class SubscriptionSnapshot(Base, TimestampedModel):
    __tablename__ = "subscription_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ipo_id = Column(String(36), ForeignKey("ipos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    snapshot_time = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    qib_subscription_times = Column(Float, nullable=True)
    nii_subscription_times = Column(Float, nullable=True)
    rii_subscription_times = Column(Float, nullable=True)
    employee_subscription_times = Column(Float, nullable=True)
    total_subscription_times = Column(Float, nullable=True)
    total_shares_bid = Column(BigInteger, nullable=True)

    ipo = relationship("IPO", back_populates="subscriptions")
