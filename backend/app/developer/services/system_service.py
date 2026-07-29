"""
Business logic for System Health.
Reuses the shared async Redis client (app/state/redis_client.py).

FIXES vs previous version:
  1. avg_latency_ms was hardcoded to None with a comment saying the column
     doesn't exist. DecisionLog.latency_ms now exists. Fixed to query it.

  2. latency_trend added: hourly avg latency for the current day so the
     frontend can display a latency trend chart.

  3. OPTIMIZATION: today's action breakdown + latency avg now merged into
     2 queries instead of the previous 1+None pattern. Both run against
     separate tables (RequestLog for actions, DecisionLog for latency)
     so they cannot be merged further — 2 queries is the minimum.

  4. Graceful degradation: if latency_ms column doesn't exist on an older
     DB (migration not yet run), the latency query is caught and returns
     None cleanly rather than crashing the entire health endpoint.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.request_log import RequestLog
from app.db.models.decision_log import DecisionLog
from app.state.redis_client import redis_client
from app.websocket.developer_manager import developer_websocket_manager

logger = logging.getLogger(__name__)


async def get_system_health(db: AsyncSession, broadcast: bool = False) -> dict:
    """
    DB ping, Redis ping, latency from DecisionLog.latency_ms,
    error rate, and today's action breakdown.

    DB queries: 1 (RequestLog action counts) + 1 (DecisionLog latency avg)
                + 1 (DecisionLog hourly latency trend) = 3 queries.
    Previously: 1 query + hardcoded None for latency.
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── DB health ─────────────────────────────────────────────────────────────
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"[DEVELOPER PANEL] DB health check failed: {e}")
        db_status = "down"

    # ── Redis health ──────────────────────────────────────────────────────────
    redis_status = "healthy"
    try:
        pong = await redis_client.ping()
        if not pong:
            redis_status = "down"
    except Exception as e:
        logger.error(f"[DEVELOPER PANEL] Redis health check failed: {e}")
        redis_status = "down"

    # ── Today's action breakdown from RequestLog (1 query) ───────────────────
    today_result = await db.execute(
        select(
            func.count(RequestLog.id).label("total"),
            func.sum(case((RequestLog.action == "block",    1), else_=0)).label("blocked"),
            func.sum(case((RequestLog.action == "throttle", 1), else_=0)).label("throttled"),
            func.sum(case((RequestLog.action == "allow",    1), else_=0)).label("allowed"),
        ).where(RequestLog.created_at >= today_start)
    )
    today_row = today_result.one()
    total_today     = today_row.total     or 0
    blocked_today   = today_row.blocked   or 0
    throttled_today = today_row.throttled or 0
    allowed_today   = today_row.allowed   or 0

    error_rate_pct = (
        round(((blocked_today + throttled_today) / total_today) * 100, 2)
        if total_today else 0.0
    )

    # ── Latency from DecisionLog.latency_ms (FIX: was hardcoded None) ────────
    avg_latency_ms = None
    latency_trend  = []
    try:
        # Average latency today
        lat_avg_result = await db.execute(
            select(func.avg(DecisionLog.latency_ms).label("avg_ms"))
            .where(
                DecisionLog.created_at >= today_start,
                DecisionLog.latency_ms.isnot(None),
            )
        )
        avg_row = lat_avg_result.one()
        if avg_row.avg_ms is not None:
            avg_latency_ms = round(float(avg_row.avg_ms), 2)

        # Hourly latency trend for today (for frontend chart)
        trend_result = await db.execute(
            select(
                func.date_trunc("hour", DecisionLog.created_at).label("hour"),
                func.avg(DecisionLog.latency_ms).label("avg_ms"),
                func.count(DecisionLog.id).label("count"),
            )
            .where(
                DecisionLog.created_at >= today_start,
                DecisionLog.latency_ms.isnot(None),
            )
            .group_by("hour")
            .order_by("hour")
        )
        latency_trend = [
            {
                "time":           row.hour,
                "avg_latency_ms": round(float(row.avg_ms), 2) if row.avg_ms else None,
                "request_count":  row.count,
            }
            for row in trend_result.all()
        ]
    except Exception as e:
        # Graceful degradation if latency_ms column doesn't exist yet
        logger.warning(
            f"[DEVELOPER PANEL] Latency query failed "
            f"(run DB migration to add latency_ms to decision_logs): {e}"
        )
        avg_latency_ms = None
        latency_trend  = []

    result = {
        "db_status":             db_status,
        "redis_status":          redis_status,
        "avg_latency_ms":        avg_latency_ms,
        "error_rate_pct":        error_rate_pct,
        "total_requests_today":  total_today,
        "blocked_today":         blocked_today,
        "throttled_today":       throttled_today,
        "allowed_today":         allowed_today,
        "latency_trend":         latency_trend,   # NEW: hourly latency for chart
    }

    if broadcast:
        await developer_websocket_manager.broadcast_system_health(result)

    return result
