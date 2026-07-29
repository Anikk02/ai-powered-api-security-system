"""
Pydantic schemas for Debug Tools.
FIX: Added latency_ms to RecentDecision and decision dict so the
frontend can display per-request latency in the Debug panel.
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.developer.schemas.logs import GlobalLogEntry


class DebugRequestInfo(BaseModel):
    request_log: GlobalLogEntry
    decision:    Optional[Dict[str, Any]] = None
    features:    Optional[Dict[str, Any]] = None


class RecentDecision(BaseModel):
    id:          int
    action:      str
    risk_score:  Optional[float] = None
    reason:      Optional[str]   = None
    explanation: Optional[str]   = None
    latency_ms:  Optional[float] = None   # FIX: populated from DecisionLog.latency_ms
    created_at:  datetime


class DebugIdentitySummary(BaseModel):
    identity_id:     str
    client_id:       Optional[int] = None
    total_requests:  int
    blocked_count:   int
    throttled_count: int
    allowed_count:   int
    is_blocked:      bool
    recent_decisions: List[RecentDecision]
