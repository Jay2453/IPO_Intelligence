from sqlalchemy import Column, String, Boolean, Date, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampedModel, generate_uuid


class ModelVersion(Base, TimestampedModel):
    __tablename__ = "model_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    model_name = Column(String(100), nullable=False)
    version_tag = Column(String(50), nullable=False, unique=True)
    algorithm = Column(String(100), nullable=False)
    training_cutoff_date = Column(Date, nullable=True)
    validation_metrics = Column(JSON, nullable=True)
    feature_manifest = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    predictions = relationship("Prediction", back_populates="model_version")
