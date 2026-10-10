from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class IPOEventResponse(BaseModel):
    id: str
    ipo_id: str
    event_type: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    headline: str
    description: Optional[str] = None
    event_timestamp: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
