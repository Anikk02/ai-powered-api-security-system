import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case, desc, between
from sqlalchemy.sql import text

from app.api.deps import get_db
from app.schemas.dashboard import (
    DashboardStatsResponse,
    TrafficResponse,
    TrafficDataPoint,
    SuspiciousUserResponse,
    AlertResponse,
    LogResponse
)
from app.db.models.request_log import RequestLog
from app.db.models.decision_log import DecisionLog
from app.db.models.feature_log import FeatureLog
from app.db.models.client import Client
from app.risk.risk_engine import get_adaptive_thresholds
from app.state.state_manager import StateManager
from app.authentication.dependencies import require_active_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


class _IdentityRef:
    """Minimal stand-in for app.identity.resolver.Identity."""
    __slots__ = ("client_id", "identity_id")

    def __init__(self, client_id: int | None, identity_id: str):
        self.client_id = client_id
        self.identity_id = identity_id


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_client: Client = Depends(require_active_client),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard stats for the authenticated client only."""
    client_id = current_client.id
    
    now = datetime.utcnow()
    last_minute = now - timedelta(minutes=1)
    prev_minute_start = last_minute - timedelta(minutes=1)
    last_15m = now - timedelta(minutes=15)
    prev_15_start = now - timedelta(minutes=30)
    prev_15_end = now - timedelta(minutes=15)
    last_60m = now - timedelta(minutes=60)

    high_th, med_th = get_adaptive_thresholds()

    # ── 1 query: RPS (current) + RPS (previous minute) ──────────
    rps_result = await db.execute(
        select(
            func.sum(case((and_(
                RequestLog.created_at >= last_minute,
                RequestLog.client_id == client_id
            ), 1), else_=0)).label("current"),
            func.sum(case((and_(
                RequestLog.created_at >= prev_minute_start,
                RequestLog.created_at < last_minute,
                RequestLog.client_id == client_id
            ), 1), else_=0)).label("previous"),
        )
        .where(RequestLog.created_at >= prev_minute_start)
    )
    rps_row = rps_result.one()
    requests_last_minute = rps_row.current or 0
    prev_requests = rps_row.previous or 0

    requests_per_second = round(requests_last_minute / 60, 1)
    prev_rps = prev_requests / 60 if prev_requests > 0 else 1
    rps_trend = round(((requests_per_second - prev_rps) / max(prev_rps, 0.01)) * 100, 1)

    # ── 2 query: violations, risk composition, avg risk, latency ───────────
    dec_result = await db.execute(
        select(
            # Violations - ACTUAL blocked + throttled decisions
            func.sum(case((and_(
                DecisionLog.created_at >= last_15m,
                DecisionLog.action.in_(["block", "throttle"]),
                DecisionLog.client_id == client_id
            ), 1), else_=0)).label("violations"),
            func.sum(case((and_(
                DecisionLog.created_at >= prev_15_start,
                DecisionLog.created_at < prev_15_end,
                DecisionLog.action.in_(["block", "throttle"]),
                DecisionLog.client_id == client_id
            ), 1), else_=0)).label("prev_violations"),
            
            # Risk composition - based on ACTUAL decisions, not thresholds
            func.sum(case((and_(
                DecisionLog.created_at >= last_15m,
                DecisionLog.action == "block",
                DecisionLog.client_id == client_id
            ), 1), else_=0)).label("block_count"),
            func.sum(case((and_(
                DecisionLog.created_at >= last_15m,
                DecisionLog.action == "throttle",
                DecisionLog.client_id == client_id
            ), 1), else_=0)).label("throttle_count"),
            func.sum(case((and_(
                DecisionLog.created_at >= last_15m,
                DecisionLog.action == "allow",
                DecisionLog.client_id == client_id
            ), 1), else_=0)).label("allow_count"),
            
            # Avg risk
            func.avg(case((and_(
                DecisionLog.created_at >= last_15m,
                DecisionLog.client_id == client_id
            ), DecisionLog.risk_score), else_=None)).label("avg_risk"),
            func.avg(case((and_(
                DecisionLog.created_at >= prev_15_start,
                DecisionLog.created_at < prev_15_end,
                DecisionLog.client_id == client_id
            ), DecisionLog.risk_score), else_=None)).label("prev_avg_risk"),

            # LATENCY: Current avg (last 15m)
            func.avg(case((and_(
                DecisionLog.created_at >= last_15m,
                DecisionLog.latency_ms.isnot(None),
                DecisionLog.client_id == client_id
            ), DecisionLog.latency_ms), else_=None)).label("avg_latency"),
            
            # LATENCY: Previous avg (prev 15m)
            func.avg(case((and_(
                DecisionLog.created_at >= prev_15_start,
                DecisionLog.created_at < prev_15_end,
                DecisionLog.latency_ms.isnot(None),
                DecisionLog.client_id == client_id
            ), DecisionLog.latency_ms), else_=None)).label("prev_avg_latency"),
            
            # Total requests (count of all decisions in last 15m)
            func.count().label("total_requests_15m"),
            
            # Previous total requests (count of all decisions in prev 15m)
            func.count(case((and_(
                DecisionLog.created_at >= prev_15_start,
                DecisionLog.created_at < prev_15_end,
                DecisionLog.client_id == client_id
            ), 1), else_=None)).label("prev_total_requests"),
            
            # Blocked count in last 15m - ACTUAL block decisions
            func.count(case((and_(
                DecisionLog.created_at >= last_15m,
                DecisionLog.action == "block",
                DecisionLog.client_id == client_id
            ), 1), else_=None)).label("blocked_count"),
            
            # Previous blocked count
            func.count(case((and_(
                DecisionLog.created_at >= prev_15_start,
                DecisionLog.created_at < prev_15_end,
                DecisionLog.action == "block",
                DecisionLog.client_id == client_id
            ), 1), else_=None)).label("prev_blocked_count"),
            
            # Throttled count in last 15m - ACTUAL throttle decisions
            func.count(case((and_(
                DecisionLog.created_at >= last_15m,
                DecisionLog.action == "throttle",
                DecisionLog.client_id == client_id
            ), 1), else_=None)).label("throttled_count"),
            
            # Previous throttled count
            func.count(case((and_(
                DecisionLog.created_at >= prev_15_start,
                DecisionLog.created_at < prev_15_end,
                DecisionLog.action == "throttle",
                DecisionLog.client_id == client_id
            ), 1), else_=None)).label("prev_throttled_count"),
            
            # New users in last 15m
            func.count(func.distinct(case((and_(
                DecisionLog.created_at >= last_15m,
                DecisionLog.client_id == client_id
            ), DecisionLog.identity_id), else_=None))).label("new_users_15m"),
            
            # Previous new users
            func.count(func.distinct(case((and_(
                DecisionLog.created_at >= prev_15_start,
                DecisionLog.created_at < prev_15_end,
                DecisionLog.client_id == client_id
            ), DecisionLog.identity_id), else_=None))).label("prev_new_users"),
        )
        .where(DecisionLog.created_at >= prev_15_start)
    )
    dec_row = dec_result.one()

    violations = dec_row.violations or 0
    prev_violations = dec_row.prev_violations or 0
    block_count = dec_row.block_count or 0
    throttle_count = dec_row.throttle_count or 0
    allow_count = dec_row.allow_count or 0
    avg_risk_score = round(dec_row.avg_risk or 0, 2)
    prev_avg_risk = dec_row.prev_avg_risk or 0.01

    # Extract latency values
    avg_latency_ms = dec_row.avg_latency or 0.0
    prev_avg_latency_ms = dec_row.prev_avg_latency or 0.0

    # Extract 15-minute metrics
    total_requests_15m = dec_row.total_requests_15m or 0
    prev_total_requests = dec_row.prev_total_requests or 0
    blocked_count_15m = dec_row.blocked_count or 0
    prev_blocked_count = dec_row.prev_blocked_count or 0
    throttled_count_15m = dec_row.throttled_count or 0
    prev_throttled_count = dec_row.prev_throttled_count or 0
    new_users_15m = dec_row.new_users_15m or 0
    prev_new_users = dec_row.prev_new_users or 0

    # ── 3 query: suspicious sessions (ACTUAL blocked/throttled identities) ──
    sess_result = await db.execute(
        select(func.count(func.distinct(DecisionLog.identity_id)))
        .where(and_(
            DecisionLog.created_at >= last_15m,
            DecisionLog.action.in_(["block", "throttle"]),
            DecisionLog.identity_id.isnot(None),
            DecisionLog.client_id == client_id
        ))
    )
    suspicious_sessions = sess_result.scalar() or 0

    # ── 4 query: decisions last minute (for the small widget) ──
    dec_last_min_result = await db.execute(
        select(
            func.sum(case((and_(
                DecisionLog.created_at >= last_minute,
                DecisionLog.action == "allow",
                DecisionLog.client_id == client_id
            ), 1), else_=0)).label("allowed"),
            func.sum(case((and_(
                DecisionLog.created_at >= last_minute,
                DecisionLog.action == "throttle",
                DecisionLog.client_id == client_id
            ), 1), else_=0)).label("throttled"),
            func.sum(case((and_(
                DecisionLog.created_at >= last_minute,
                DecisionLog.action == "block",
                DecisionLog.client_id == client_id
            ), 1), else_=0)).label("blocked"),
        )
        .where(DecisionLog.created_at >= last_minute)
    )
    dec_min_row = dec_last_min_result.one()
    decisions_last_min = {
        "allowed": dec_min_row.allowed or 0,
        "throttled": dec_min_row.throttled or 0,
        "blocked": dec_min_row.blocked or 0
    }

    # ── Calculate trends (all using 15-minute windows) ───────────
    if prev_violations > 0:
        violations_trend = int(((violations - prev_violations) / prev_violations) * 100)
    else:
        violations_trend = violations * 100 if violations > 0 else 0

    # Risk trend
    risk_trend = round(
        ((avg_risk_score - prev_avg_risk) / max(prev_avg_risk, 0.01)) * 100, 1
    )

    # LATENCY trend
    if prev_avg_latency_ms > 0:
        latency_trend = round(
            ((avg_latency_ms - prev_avg_latency_ms) / prev_avg_latency_ms) * 100, 1
        )
    else:
        latency_trend = 0.0
    
    # Format latency for display
    if avg_latency_ms < 1:
        avg_latency = f"{round(avg_latency_ms * 1000)} μs"
    else:
        avg_latency = f"{round(avg_latency_ms, 1)} ms"

    # Total requests trend (15-minute window)
    if prev_total_requests > 0:
        total_requests_trend = round(
            ((total_requests_15m - prev_total_requests) / prev_total_requests) * 100, 1
        )
    else:
        total_requests_trend = 0.0

    # Blocked trend (15-minute window)
    if prev_blocked_count > 0:
        blocked_trend = round(
            ((blocked_count_15m - prev_blocked_count) / prev_blocked_count) * 100, 1
        )
    else:
        blocked_trend = 0.0

    # Throttled trend (15-minute window)
    if prev_throttled_count > 0:
        throttled_trend = round(
            ((throttled_count_15m - prev_throttled_count) / prev_throttled_count) * 100, 1
        )
    else:
        throttled_trend = 0.0

    # New users trend (15-minute window)
    if prev_new_users > 0:
        new_users_trend = round(
            ((new_users_15m - prev_new_users) / prev_new_users) * 100, 1
        )
    else:
        new_users_trend = 0.0

    # ── Traffic composition based on ACTUAL decisions ───────────
    total = block_count + throttle_count + allow_count
    traffic_composition = {
        "normal": round((allow_count / total) * 100) if total else 0,
        "suspicious": round((throttle_count / total) * 100) if total else 0,
        "high_risk": round((block_count / total) * 100) if total else 0,
    }

    return DashboardStatsResponse(
        requests_per_second=requests_per_second,
        requests_trend=rps_trend,
        violations_detected=violations,
        violations_trend=violations_trend,
        suspicious_sessions=suspicious_sessions,
        sessions_trend=0,
        traffic_composition=traffic_composition,
        avg_risk_score=avg_risk_score,
        risk_trend=risk_trend,
        avg_latency=avg_latency,
        latency_trend=latency_trend,
        active_users_15m=new_users_15m,  # 15-minute data
        active_users_trend=new_users_trend,
        blocked_trend=blocked_trend,
        throttled_trend=throttled_trend,
        decisions_last_min=decisions_last_min, #1-minute for the small widget
        total_requests_15m=total_requests_15m,  
        total_requests_trend=total_requests_trend,
        blocked_count_15m=blocked_count_15m, 
        throttled_count_15m=throttled_count_15m,
    )


@router.get("/traffic", response_model=TrafficResponse)
async def get_traffic_data(
    current_client: Client = Depends(require_active_client),
    timeframe: str = Query("15m", regex="^(15m|1h|6h|24h)$"),
    db: AsyncSession = Depends(get_db)
):
    """Get traffic data for the authenticated client only."""
    client_id = current_client.id
    
    now = datetime.utcnow()

    # Configure timeframe parameters
    if timeframe == "15m":
        trunc_unit = "minute"
        points = 15
        start_time = now - timedelta(minutes=15)
        interval_minutes = 1
    elif timeframe == "1h":
        trunc_unit = "minute"
        points = 12
        start_time = now - timedelta(hours=1)
        interval_minutes = 5
    elif timeframe == "6h":
        trunc_unit = "hour"
        points = 6
        start_time = now - timedelta(hours=6)
        interval_minutes = 60
    else:  # 24h
        trunc_unit = "hour"
        points = 24
        start_time = now - timedelta(hours=24)
        interval_minutes = 60

    # ── Query: requests ──────────────────────────────────────
    request_rows = (await db.execute(
        select(
            func.date_trunc(trunc_unit, RequestLog.created_at).label("bucket"),
            func.count().label("cnt")
        )
        .where(and_(
            RequestLog.created_at >= start_time,
            RequestLog.client_id == client_id
        ))
        .group_by("bucket")
        .order_by("bucket")
    )).all()

    # ── Query: blocked (ACTUAL block decisions) ──────────────
    blocked_rows = (await db.execute(
        select(
            func.date_trunc(trunc_unit, DecisionLog.created_at).label("bucket"),
            func.count().label("cnt")
        )
        .where(and_(
            DecisionLog.created_at >= start_time,
            DecisionLog.action == "block",
            DecisionLog.client_id == client_id
        ))
        .group_by("bucket")
        .order_by("bucket")
    )).all()

    # ── Query: throttled (ACTUAL throttle decisions) ───────────────
    throttled_rows = (await db.execute(
        select(
            func.date_trunc(trunc_unit, DecisionLog.created_at).label("bucket"),
            func.count().label("cnt")
        )
        .where(and_(
            DecisionLog.created_at >= start_time,
            DecisionLog.action == "throttle",
            DecisionLog.client_id == client_id
        ))
        .group_by("bucket")
        .order_by("bucket")
    )).all()

    req_by_bucket = {row.bucket: row.cnt for row in request_rows}
    blocked_by_bucket = {row.bucket: row.cnt for row in blocked_rows}
    throttled_by_bucket = {row.bucket: row.cnt for row in throttled_rows}

    data_points = []
    for i in range(points):
        bucket_start = start_time + timedelta(minutes=interval_minutes * i)
        bucket_end = bucket_start + timedelta(minutes=interval_minutes)

        # Aggregate for 1h timeframe (5-minute buckets)
        if timeframe == "1h":
            requests = sum(
                v for k, v in req_by_bucket.items()
                if bucket_start <= k < bucket_end
            )
            blocked = sum(
                v for k, v in blocked_by_bucket.items()
                if bucket_start <= k < bucket_end
            )
            throttled = sum(
                v for k, v in throttled_by_bucket.items()
                if bucket_start <= k < bucket_end
            )
        else:
            requests = req_by_bucket.get(bucket_start, 0)
            blocked = blocked_by_bucket.get(bucket_start, 0)
            throttled = throttled_by_bucket.get(bucket_start, 0)

        data_points.append(TrafficDataPoint(
            time=bucket_start,
            requests=requests,
            anomalies=throttled,  # Using throttled as anomalies
            blocked=blocked
        ))

    return TrafficResponse(data=data_points, timeframe=timeframe)

@router.get("/suspicious-users", response_model=List[SuspiciousUserResponse])
async def get_suspicious_users(
    current_client: Client = Depends(require_active_client),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get suspicious users for the authenticated client only."""
    client_id = current_client.id
    
    now = datetime.utcnow()
    last_15m = now - timedelta(minutes=15)

    # Rank each identity's decisions by recency so we can pull the
    # TRUE latest action/reason - func.max() on a string column sorts
    # alphabetically ("throttle" > "block" > "allow"), not chronologically,
    # so a user throttled-then-blocked in the same window would incorrectly
    # report "throttle" as their latest action.
    ranked = (
        select(
            DecisionLog.identity_id.label("identity_id"),
            DecisionLog.action.label("action"),
            DecisionLog.explanation.label("explanation"),
            DecisionLog.created_at.label("created_at"),
            func.row_number().over(
                partition_by=DecisionLog.identity_id,
                order_by=DecisionLog.created_at.desc(),
            ).label("rn"),
        )
        .where(and_(
            DecisionLog.created_at >= last_15m,
            DecisionLog.action.in_(["block", "throttle"]),
            DecisionLog.identity_id.isnot(None),
            DecisionLog.client_id == client_id
        ))
        .subquery()
    )
    latest = (
        select(
            ranked.c.identity_id,
            ranked.c.action.label("latest_action"),
            ranked.c.explanation.label("latest_reason"),
        )
        .where(ranked.c.rn == 1)
        .subquery()
    )

    result = await db.execute(
        select(
            DecisionLog.identity_id.label("identity_id"),
            func.min(RequestLog.ip_address).label("ip"),
            func.max(DecisionLog.risk_score).label("max_risk"),
            func.max(DecisionLog.created_at).label("last_seen"),
            func.count(DecisionLog.id).label("violations"),
            func.max(latest.c.latest_action).label("latest_action"),
            func.max(latest.c.latest_reason).label("reason"),
        )
        .select_from(DecisionLog)
        .join(RequestLog, DecisionLog.request_id == RequestLog.id)
        .join(latest, latest.c.identity_id == DecisionLog.identity_id)
        .where(and_(
            DecisionLog.created_at >= last_15m,
            DecisionLog.action.in_(["block", "throttle"]),  # ACTUAL blocked/throttled
            DecisionLog.identity_id.isnot(None),
            DecisionLog.client_id == client_id
        ))
        .group_by(DecisionLog.identity_id)
        .order_by(func.max(DecisionLog.risk_score).desc())
        .limit(limit)
    )

    suspicious_users = []
    for row in result.all():
        identity_id = row.identity_id
        ip = row.ip or "unknown"
        risk_score = row.max_risk or 0
        last_seen = row.last_seen
        violations = row.violations or 0
        reason = row.reason
        latest_action = row.latest_action

        is_blocked = latest_action == "block"
        is_throttled = latest_action == "throttle"

        # Determine status - actual enforcement state takes priority
        # over the risk-score bucket, otherwise a blocked user can show
        # as merely "high_risk" if their risk score happens to fall
        # short of the "critical" cutoff.
        high_th, med_th = get_adaptive_thresholds()
        if is_blocked:
            status = "blocked"
        elif is_throttled:
            status = "throttled"
        elif risk_score > high_th + 0.1:
            status = "critical"
        elif risk_score > high_th:
            status = "high_risk"
        elif risk_score > med_th:
            status = "elevated"
        else:
            status = "low"

        suspicious_users.append(SuspiciousUserResponse(
            id=identity_id,
            identity_id=identity_id,
            violations=violations,
            threat_score=round(risk_score, 2),
            status=status,
            ip=ip,
            last_seen=last_seen,
            reason=reason or "No reason",
            is_blocked=is_blocked,
        ))

    return suspicious_users


@router.get("/alerts", response_model=List[AlertResponse])
async def get_recent_alerts(
    current_client: Client = Depends(require_active_client),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get alerts for the authenticated client only."""
    client_id = current_client.id
    
    now = datetime.utcnow()
    last_15m = now - timedelta(minutes=15)

    result = await db.execute(
        select(
            DecisionLog.id,
            RequestLog.ip_address,
            DecisionLog.risk_score,
            DecisionLog.action,
            DecisionLog.reason,
            DecisionLog.created_at,
            DecisionLog.identity_id
        )
        .join(RequestLog, DecisionLog.request_id == RequestLog.id)
        .where(and_(
            DecisionLog.created_at >= last_15m,
            DecisionLog.action.in_(["block", "throttle"]),  # ACTUAL blocked/throttled
            RequestLog.client_id == client_id
        ))
        .order_by(DecisionLog.risk_score.desc())
        .limit(limit)
    )

    alerts = []
    for row in result.all():
        risk_score = row[2] or 0
        action = row[3]

        if action == "block":
            alert_type = "Blocked Threat"
        elif action == "throttle":
            alert_type = "Rate Limited Threat"
        else:
            alert_type = "High Risk Activity"

        alerts.append(AlertResponse(
            id=row[0],
            ip=row[1] or "unknown",
            score=round(risk_score, 2),
            type=alert_type,
            timestamp=row[5],
            identity_id=row[6],
        ))

    return alerts


@router.get("/logs", response_model=List[LogResponse])
async def get_decision_logs(
    current_client: Client = Depends(require_active_client),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get logs for the authenticated client only."""
    client_id = current_client.id
    
    offset = (page - 1) * limit
    high_th, med_th = get_adaptive_thresholds()

    result = await db.execute(
        select(
            DecisionLog.id,
            DecisionLog.request_uuid,
            DecisionLog.identity_id,
            RequestLog.endpoint,
            RequestLog.ip_address,
            DecisionLog.action,
            DecisionLog.risk_score,
            DecisionLog.reason,
            DecisionLog.explanation,
            DecisionLog.explanation_json,
            DecisionLog.created_at
        )
        .join(RequestLog, DecisionLog.request_id == RequestLog.id)
        .where(RequestLog.client_id == client_id)
        .order_by(DecisionLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    logs = []
    for row in result.all():
        risk_score = row[6] or 0

        logs.append(LogResponse(
            id=row[0],
            request_uuid=row[1],
            identity_id=row[2],
            endpoint=row[3],
            ip_address=row[4] or "unknown",
            action=row[5],
            risk_score=round(risk_score, 2),
            explanation={
                "summary": row[8] or row[7] or "No explanation",
                "details": row[9] or {}
            },
            created_at=row[10],
        ))

    return logs


@router.get("/user/{user_id}", response_model=dict)
async def get_user_details(
    user_id: str,
    current_client: Client = Depends(require_active_client),
    client_id: int | None = Query(None, description="Client/tenant ID that owns this identity, if known"),
    db: AsyncSession = Depends(get_db)
):
    """Get user details for the authenticated client only."""
    auth_client_id = current_client.id
    identity_id = user_id
    
    # Verify the user belongs to the authenticated client
    if client_id is not None and client_id != auth_client_id:
        raise HTTPException(status_code=403, detail="Access denied to this client's data")
    
    now = datetime.utcnow()
    last_15m = now - timedelta(minutes=15)
    high_th, med_th = get_adaptive_thresholds()

    # Verify user belongs to this client if client_id not provided
    if client_id is None:
        result = await db.execute(
            select(RequestLog.client_id)
            .where(RequestLog.identity_id == identity_id)
            .order_by(RequestLog.created_at.desc())
            .limit(1)
        )
        resolved_client_id = result.scalar()
        if resolved_client_id is not None and resolved_client_id != auth_client_id:
            raise HTTPException(status_code=403, detail="Access denied to this user's data")
        client_id = resolved_client_id

    # ── 1 query: total requests ──
    total_result = await db.execute(
        select(func.count(RequestLog.id))
        .where(and_(
            RequestLog.identity_id == identity_id,
            RequestLog.client_id == auth_client_id
        ))
    )
    total_requests = total_result.scalar() or 0

    # ── 2 query: violations and risk ──
    risk_result = await db.execute(
        select(
            func.sum(case((DecisionLog.risk_score > med_th, 1), else_=0)).label("violations"),
            func.max(DecisionLog.risk_score).label("max_risk"),
            func.avg(DecisionLog.risk_score).label("avg_risk"),
        )
        .where(and_(
            DecisionLog.identity_id == identity_id,
            DecisionLog.created_at >= last_15m,
            DecisionLog.client_id == auth_client_id
        ))
    )
    risk_row = risk_result.one()
    
    violations = risk_row.violations or 0
    current_risk = risk_row.max_risk or 0
    avg_risk = risk_row.avg_risk or 0

    # ── 3 query: recent actions ──
    actions_result = await db.execute(
        select(DecisionLog.action, DecisionLog.created_at,
               DecisionLog.reason, DecisionLog.risk_score)
        .where(and_(
            DecisionLog.identity_id == identity_id,
            DecisionLog.client_id == auth_client_id
        ))
        .order_by(DecisionLog.created_at.desc())
        .limit(10)
    )
    recent_actions = [
        {"action": row[0], "timestamp": row[1], "reason": row[2], "risk_score": row[3]}
        for row in actions_result.all()
    ]

    # ── 4 query: IP history ──
    ip_result = await db.execute(
        select(RequestLog.ip_address)
        .where(and_(
            RequestLog.identity_id == identity_id,
            RequestLog.client_id == auth_client_id
        ))
        .distinct()
        .limit(10)
    )
    ip_history = [row[0] for row in ip_result.all() if row[0]]

    # ── Redis: block state ──
    is_blocked = await StateManager.is_blocked(_IdentityRef(client_id, identity_id))

    return {
        "identity_id": identity_id,
        "client_id": client_id,
        "is_anonymous": client_id is None,
        "total_requests": total_requests,
        "violations": violations,
        "current_risk_score": round(current_risk, 2),
        "avg_risk_score": round(avg_risk, 2),
        "is_blocked": is_blocked,
        "recent_actions": recent_actions,
        "ip_history": ip_history,
    }


@router.get("/ip/{ip}/trend")
async def get_ip_trend(
    ip: str,
    current_client: Client = Depends(require_active_client),
    db: AsyncSession = Depends(get_db)
):
    """Get IP trend data for the authenticated client only."""
    client_id = current_client.id
    
    last_1h = datetime.utcnow() - timedelta(hours=1)

    result = await db.execute(
        select(DecisionLog.created_at, DecisionLog.risk_score)
        .join(RequestLog, DecisionLog.request_id == RequestLog.id)
        .where(and_(
            RequestLog.ip_address == ip,
            DecisionLog.created_at >= last_1h,
            RequestLog.client_id == client_id
        ))
        .order_by(DecisionLog.created_at)
    )

    return [{"time": row[0], "risk": row[1]} for row in result.all()]


@router.post("/user/{user_id}/block")
async def block_user(
    user_id: str,
    current_client: Client = Depends(require_active_client),
    duration: int = Query(3600, description="Block duration in seconds"),
    client_id: int | None = Query(None, description="Client/tenant ID that owns this identity, if known"),
    db: AsyncSession = Depends(get_db)
):
    """Block an identity for the specified duration."""
    auth_client_id = current_client.id
    identity_id = user_id
    
    # Verify user belongs to this client
    if client_id is not None and client_id != auth_client_id:
        raise HTTPException(status_code=403, detail="Access denied to this user")
    
    if client_id is None:
        result = await db.execute(
            select(RequestLog.client_id)
            .where(RequestLog.identity_id == identity_id)
            .order_by(RequestLog.created_at.desc())
            .limit(1)
        )
        resolved_client_id = result.scalar()
        if resolved_client_id is not None and resolved_client_id != auth_client_id:
            raise HTTPException(status_code=403, detail="Access denied to this user")
        client_id = resolved_client_id
    
    try:
        await StateManager.block_identity(_IdentityRef(client_id, identity_id), duration)
        logger.info(f"Identity {identity_id} blocked for {duration} seconds by client {auth_client_id}")
        return {
            "success": True,
            "message": f"Identity {identity_id} blocked for {duration} seconds",
            "identity_id": identity_id,
            "duration": duration,
        }
    except Exception as e:
        logger.error(f"Failed to block identity {identity_id}: {e}")
        return {"success": False, "error": str(e)}


@router.post("/user/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    current_client: Client = Depends(require_active_client),
    client_id: int | None = Query(None, description="Client/tenant ID that owns this identity, if known"),
    db: AsyncSession = Depends(get_db)
):
    """Unblock an identity."""
    auth_client_id = current_client.id
    identity_id = user_id
    
    # Verify user belongs to this client
    if client_id is not None and client_id != auth_client_id:
        raise HTTPException(status_code=403, detail="Access denied to this user")
    
    if client_id is None:
        result = await db.execute(
            select(RequestLog.client_id)
            .where(RequestLog.identity_id == identity_id)
            .order_by(RequestLog.created_at.desc())
            .limit(1)
        )
        resolved_client_id = result.scalar()
        if resolved_client_id is not None and resolved_client_id != auth_client_id:
            raise HTTPException(status_code=403, detail="Access denied to this user")
        client_id = resolved_client_id
    
    try:
        base = StateManager._base(client_id, identity_id)
        await StateManager.delete(f"{base}:blocked")
        logger.info(f"Identity {identity_id} unblocked by client {auth_client_id}")
        return {
            "success": True,
            "message": f"Identity {identity_id} unblocked",
            "identity_id": identity_id,
        }
    except Exception as e:
        logger.error(f"Failed to unblock identity {identity_id}: {e}")
        return {"success": False, "error": str(e)}
    

# Most Triggered Policies
@router.get("/top-policies", response_model=List[dict])
async def get_top_policies(
    current_client: Client = Depends(require_active_client),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db)
):
    """Get most triggered policies based on feature data."""
    client_id = current_client.id
    
    now = datetime.utcnow()
    last_15m = now - timedelta(minutes=15)
    
    # Query features from the last 15 minutes
    result = await db.execute(
        select(
            FeatureLog.features,
            DecisionLog.risk_score,
            DecisionLog.action
        )
        .join(DecisionLog, FeatureLog.request_id == DecisionLog.id)
        .where(and_(
            FeatureLog.created_at >= last_15m,
            FeatureLog.client_id == client_id,
            DecisionLog.risk_score > 0.1  # Only include non-trivial risk
        ))
        .order_by(DecisionLog.risk_score.desc())
        .limit(1000)  # Sample size
    )
    
    features = result.all()
    
    # Aggregate policy triggers
    policy_counts = {}
    policy_risk_scores = {}
    policy_actions = {}
    
    for feature_row in features:
        feature_data = feature_row.features or {}
        risk_score = feature_row.risk_score or 0
        action = feature_row.action or "allow"
        
        # Determine which policy was triggered based on feature values
        policies_triggered = _extract_policies_from_features(feature_data)
        
        for policy in policies_triggered:
            if policy not in policy_counts:
                policy_counts[policy] = 0
                policy_risk_scores[policy] = []
                policy_actions[policy] = {"allow": 0, "block": 0, "throttle": 0}
            
            policy_counts[policy] += 1
            policy_risk_scores[policy].append(risk_score)
            if action in policy_actions[policy]:
                policy_actions[policy][action] += 1
    
    # Calculate percentages and format response
    total_triggers = sum(policy_counts.values()) or 1
    policies = []
    
    for policy_name, count in sorted(policy_counts.items(), key=lambda x: x[1], reverse=True)[:limit]:
        avg_risk = sum(policy_risk_scores[policy_name]) / len(policy_risk_scores[policy_name]) if policy_risk_scores[policy_name] else 0
        action_counts = policy_actions[policy_name]
        total_actions = sum(action_counts.values()) or 1
        
        policies.append({
            "name": policy_name,
            "trigger_count": count,
            "percentage": round((count / total_triggers) * 100, 1),
            "avg_risk_score": round(avg_risk, 2),
            "allowed": round((action_counts.get("allow", 0) / total_actions) * 100),
            "blocked": round((action_counts.get("block", 0) / total_actions) * 100),
            "throttled": round((action_counts.get("throttle", 0) / total_actions) * 100),
        })
    
    return policies


def _extract_policies_from_features(features: dict) -> List[str]:
    """Extract triggered policies based on feature values."""
    policies = []
    
    # Bot Detection
    if features.get("is_bot", 0) > 0.5:
        policies.append("Bot Detection")
    
    # Rate Limiting
    if features.get("is_rate_limited", 0) > 0:
        policies.append("Rate Limit Exceeded")
    
    # Burst Detection
    if features.get("burst_score", 0) > 0.5:
        policies.append("Burst Traffic")
    
    # Suspicious User Agent
    if features.get("is_suspicious_ua", 0) > 0:
        policies.append("Suspicious UA")
    
    # High Error Rate
    if features.get("error_rate", 0) > 0.3:
        policies.append("High Error Rate")
    
    # IP Changes
    if features.get("ip_changes", 0) > 3:
        policies.append("IP Rotation")
    
    # Sensitive Data Access
    if features.get("sensitive_hits", 0) > 0:
        policies.append("Sensitive Data Access")
    
    # Endpoint Entropy (random scanning)
    if features.get("endpoint_entropy", 0) > 0.5:
        policies.append("Endpoint Scanning")
    
    # Request Regularity (bot-like behavior)
    if features.get("request_regularity", 0) > 0.8:
        policies.append("Bot-like Behavior")
    
    # Rate of requests
    if features.get("req_per_min", 0) > 60:
        policies.append("High Request Rate")
    
    # If no specific policy triggered, but risk score is high
    if features.get("risk_score", 0) > 0.5 and not policies:
        policies.append("Behavioral Anomaly")
    
    return policies