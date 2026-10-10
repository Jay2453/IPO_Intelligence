from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: str
    ipo_id: str
    document_type: str
    version_number: int
    file_name: str
    file_url: str
    file_hash_sha256: str
    file_size_bytes: Optional[int] = None
    filing_date: Optional[date] = None
    is_current: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
