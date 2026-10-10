from datetime import date, datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: str
    ipo_id: Optional[str] = None
    issuer_name: Optional[str] = None
    document_type: str
    version_number: int
    file_name: str
    file_url: str
    source_url: Optional[str] = None
    file_hash_sha256: str
    file_size_bytes: Optional[int] = None
    filing_date: Optional[date] = None
    retrieval_timestamp: Optional[datetime] = None
    is_current: bool
    extraction_status: str = "PENDING"
    extraction_error: Optional[str] = None
    extracted_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

