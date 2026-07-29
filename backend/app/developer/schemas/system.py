"""
Pydantic schema for System Health.
FIX: Added latency_trend field for hourly latency chart on frontend.
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class LatencyTrendPoint(BaseModel):
    time: datetime
    avg_latency_ms: Optional[float] = None
    request_count: int


class SystemHealthResponse(BaseModel):
    db_status: str            # healthy | down
    redis_status: str         # healthy | down
    avg_latency_ms: Optional[float] = None
    error_rate_pct: float
    total_requests_today: int
    blocked_today: int
    throttled_today: int
    allowed_today: int
    latency_trend: List[LatencyTrendPoint] = []  # hourly latency points for chart
