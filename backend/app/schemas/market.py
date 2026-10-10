from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class MarketObservationResponse(BaseModel):
    id: str
    ipo_id: str
    observation_type: str
    observation_time: datetime
    gmp_inr: Optional[float] = None
    gmp_percent: Optional[float] = None
    final_issue_price_inr: Optional[float] = None
    listing_open_price_inr: Optional[float] = None
    listing_close_price_inr: Optional[float] = None
    listing_gain_pct: Optional[float] = None
    bhavcopy_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
