import json
from typing import List, Dict
from datetime import datetime, timedelta

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.request_log import RequestLog
from app.activity.schemas import SpikeCorrelation

# Still used by get_hourly_patterns() below, which is not part of the
# Postgres-backed activity pipeline and is left untouched for now.
from app.state.redis_client import redis_client


def compute_risk(blocked: int, total: int):
    if total == 0:
        return "LOW", 0.0

    percent = (blocked / total) * 100

    if percent < 30:
        return "LOW", percent
    elif percent < 60:
        return "MEDIUM", percent
    return "HIGH", percent


def compute_health(allowed: int, blocked: int):
    total = allowed + blocked
    if total == 0:
        return "HEALTHY", 100.0

    score = (allowed / total) * 100

    if score > 80:
        status = "HEALTHY"
    elif score > 50:
        status = "WARNING"
    else:
        status = "CRITICAL"

    return status, score


def compute_severity(blocked: int):
    if blocked > 100:
        return "SEVERE"
    elif blocked > 50:
        return "HIGH"
    elif blocked > 20:
        return "MEDIUM"
    return "LOW"


async def detect_spike_correlations(
    db: AsyncSession, client_id: int, time_window: int = 600
) -> List[SpikeCorrelation]:
    """
    Detect and correlate traffic spikes with endpoint targeting.

    Backed by Postgres request_logs instead of Redis. Buckets requests
    by minute, flags minutes where traffic exceeds 2x the window's
    average (and a minimum floor), then looks up the top targeted
    endpoint within each flagged minute.
    """
    try:
        window_start = datetime.utcnow() - timedelta(seconds=time_window)
        minute_bucket = func.date_trunc("minute", RequestLog.created_at).label("minute")

        minute_rows = (
            await db.execute(
                select(
                    minute_bucket,
                    func.count(RequestLog.id).label("total"),
                )
                .where(
                    RequestLog.client_id == client_id,
                    RequestLog.created_at >= window_start,
                )
                .group_by(minute_bucket)
                .order_by(minute_bucket)
            )
        ).all()

        if not minute_rows:
            return []

        totals = [row.total for row in minute_rows if row.total > 0]
        if not totals:
            return []

        avg_traffic = sum(totals) / len(totals)

        correlations: List[SpikeCorrelation] = []

        for row in minute_rows:
            if row.total > avg_traffic * 2 and row.total > 20:
                minute_start = row.minute
                minute_end = minute_start + timedelta(minutes=1)

                top_endpoint_row = (
                    await db.execute(
                        select(
                            RequestLog.endpoint,
                            func.count(RequestLog.id).label("requests"),
                            func.sum(
                                case((RequestLog.action == "block", 1), else_=0)
                            ).label("blocked"),
                        )
                        .where(
                            RequestLog.client_id == client_id,
                            RequestLog.created_at >= minute_start,
                            RequestLog.created_at < minute_end,
                        )
                        .group_by(RequestLog.endpoint)
                        .order_by(func.count(RequestLog.id).desc())
                        .limit(1)
                    )
                ).first()

                if top_endpoint_row:
                    correlations.append(
                        SpikeCorrelation(
                            peak_time=minute_start.strftime("%H:%M"),
                            blocked=top_endpoint_row.blocked or 0,
                            target=top_endpoint_row.endpoint,
                        )
                    )

        # Sort by blocked count (most severe first), limit to top 5
        correlations.sort(key=lambda x: x.blocked, reverse=True)
        return correlations[:5]

    except Exception:
        # Return empty list on error
        return []


async def get_hourly_patterns(client_id: int) -> Dict[str, float]:
    """
    Get attack patterns across endpoints for the last hour.

    NOTE: still Redis-backed. Not currently used by the Postgres-backed
    activity dashboard (activity/service.py) — left as-is since it's
    out of scope for that migration. Flag if this should move too.
    """
    patterns = {}

    try:
        endpoints_key = f"client:{client_id}:endpoints"
        endpoint_data = await redis_client.zrevrange(endpoints_key, 0, 10, withscores=True)

        if endpoint_data:
            total = sum(int(score) for _, score in endpoint_data)

            for ep, score in endpoint_data:
                ep_name = ep.decode() if isinstance(ep, bytes) else ep
                count = int(score)
                percentage = (count / total * 100) if total else 0
                patterns[ep_name] = round(percentage, 2)

    except Exception:
        pass

    return patterns