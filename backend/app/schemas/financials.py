from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


class FinancialObservationResponse(BaseModel):
    id: str
    ipo_id: str
    fiscal_year: str
    period_months: int
    revenue_crores: Optional[float] = None
    ebitda_crores: Optional[float] = None
    pat_crores: Optional[float] = None
    total_assets_crores: Optional[float] = None
    net_worth_crores: Optional[float] = None
    total_liabilities_crores: Optional[float] = None
    total_debt_crores: Optional[float] = None
    operating_cash_flow_crores: Optional[float] = None
    roe_pct: Optional[float] = None
    roce_pct: Optional[float] = None
    eps_inr: Optional[float] = None
    nav_per_share_inr: Optional[float] = None
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    statement_type: str = "CONSOLIDATED"
    is_restated: bool = True
    currency: str = "INR"
    unit: str = "CRORES"
    extraction_method: str = "PDFPLUMBER_TABLE"
    verification_status: str = "EXTRACTED"
    raw_data_provenance: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

