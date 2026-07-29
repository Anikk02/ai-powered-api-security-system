"""
Pydantic schemas for the Global Logs module.

FIX: Added risk_score field. RequestLog has no risk_score column — it is
fetched via LEFT JOIN on DecisionLog.request_uuid in logs_service.py.
The schema now declares it Optional[float] so None is valid when a request
has no decision log entry (e.g. requests rejected before the engine ran).
"""
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class GlobalLogEntry(BaseModel):
    id: int
    request_uuid: Optional[str] = None
    client_id: Optional[int] = None
    identity_id: Optional[str] = None
    api_key_id: Optional[int] = None
    endpoint: str
    method: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status_code: Optional[int] = None
    action: Optional[str] = None       # allow | throttle | block
    risk_score: Optional[float] = None  # FIX: joined from DecisionLog
    created_at: datetime

    class Config:
        from_attributes = True


class GlobalLogsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    logs: List[GlobalLogEntry]
