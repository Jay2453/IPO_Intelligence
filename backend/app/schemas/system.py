from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class IntegrationStatus(BaseModel):
    name: str
    status: str  # CONNECTED, DEGRADED, NOT_CONFIGURED, FAILED
    verified: bool
    last_check_timestamp: Optional[datetime] = None
    last_successful_sync: Optional[datetime] = None
    error_count_last_24h: int = 0
    message: str


class HealthCheckResponse(BaseModel):
    status: str  # healthy, degraded, unhealthy
    database: str  # connected, disconnected
    environment: str
    timestamp: datetime
    version: str = "1.0.0"


class SystemStatusResponse(BaseModel):
    database_connected: bool
    total_ipos_tracked: int
    real_ipos_count: int
    demo_ipos_count: int
    last_successful_sync: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    recent_errors: List[str] = []
    integrations: List[IntegrationStatus] = []
    timestamp: datetime
