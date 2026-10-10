from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class IngestionJobResponse(BaseModel):
    id: str
    job_type: str
    source_system: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    records_processed: int
    error_details: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
