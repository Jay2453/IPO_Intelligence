from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class SubscriptionSnapshotResponse(BaseModel):
    id: str
    ipo_id: str
    snapshot_time: datetime
    qib_subscription_times: Optional[float] = None
    nii_subscription_times: Optional[float] = None
    rii_subscription_times: Optional[float] = None
    employee_subscription_times: Optional[float] = None
    total_subscription_times: Optional[float] = None
    total_shares_bid: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
