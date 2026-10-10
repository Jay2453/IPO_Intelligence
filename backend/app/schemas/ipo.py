from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.events import IPOEventResponse
from app.schemas.documents import DocumentResponse
from app.schemas.financials import FinancialObservationResponse
from app.schemas.subscriptions import SubscriptionSnapshotResponse
from app.schemas.market import MarketObservationResponse
from app.schemas.predictions import PredictionResponse


class IPOBase(BaseModel):
    symbol: Optional[str] = None
    company_name: str
    exchange: str = "NSE_BSE"
    category: str = "MAINBOARD"
    lifecycle_status: str = "DISCOVERED"
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    lot_size: Optional[int] = None
    issue_size_crores: Optional[float] = None
    fresh_issue_crores: Optional[float] = None
    ofs_crores: Optional[float] = None
    open_date: Optional[date] = None
    close_date: Optional[date] = None
    allotment_date: Optional[date] = None
    refund_date: Optional[date] = None
    credit_date: Optional[date] = None
    listing_date: Optional[date] = None
    face_value: Optional[float] = None
    lead_managers: Optional[str] = None
    registrar: Optional[str] = None
    data_completeness_pct: int = 0
    analysis_status: str = "PENDING"
    is_demo: bool = False


class IPOSummaryResponse(IPOBase):
    id: str
    created_at: datetime
    updated_at: datetime
    latest_gmp_inr: Optional[float] = None
    latest_gmp_percent: Optional[float] = None
    total_subscription_times: Optional[float] = None
    positive_return_prob: Optional[float] = None
    risk_decile: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class IPODetailResponse(IPOBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    events: List[IPOEventResponse] = []
    documents: List[DocumentResponse] = []
    financials: List[FinancialObservationResponse] = []
    subscriptions: List[SubscriptionSnapshotResponse] = []
    market_observations: List[MarketObservationResponse] = []
    predictions: List[PredictionResponse] = []

    model_config = ConfigDict(from_attributes=True)
