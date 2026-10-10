from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class ModelVersionResponse(BaseModel):
    id: str
    model_name: str
    version_tag: str
    algorithm: str
    training_cutoff_date: Optional[date] = None
    validation_metrics: Optional[Dict[str, Any]] = None
    feature_manifest: Optional[List[str]] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PredictionResponse(BaseModel):
    id: str
    ipo_id: str
    model_version_id: str
    prediction_timestamp: datetime
    forecast_horizon: str
    positive_return_prob: Optional[float] = None
    predicted_return_pct: Optional[float] = None
    risk_decile: Optional[int] = None
    feature_snapshot: Optional[Dict[str, Any]] = None
    evidence_summary: Optional[Dict[str, Any]] = None
    prediction_status: str
    created_at: datetime
    model_version: Optional[ModelVersionResponse] = None

    model_config = ConfigDict(from_attributes=True)
