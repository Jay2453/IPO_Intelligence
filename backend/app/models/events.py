from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid, utcnow


class IPOEvent(Base, TimestampedModel):
    __tablename__ = "ipo_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ipo_id = Column(String(36), ForeignKey("ipos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    event_type = Column(String(50), nullable=False)  # STATUS_CHANGED, RHP_FILED, DATES_ANNOUNCED, etc.
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=True)
    headline = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    ipo = relationship("IPO", back_populates="events")
