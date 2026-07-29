from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.activity.schemas import (
    ActivityResponse,
    ThreatEvent,
    DecisionTrendPoint,
    EndpointActivity,
    ActivityInsights,
    ActivityMetrics,
    PeakAttack,
    AttackPattern,
    SpikeCorrelation,
    TopEndpoint,
)

from app.activity.analyzer import (
    compute_risk,
    compute_severity,
    detect_spike_correlations,
)

from app.db.session import AsyncSessionLocal
from app.db.models.request_log import RequestLog
from app.db.models.decision_log import DecisionLog


def _event_severity(risk_score: Optional[float], action: str) -> str:
    """
    Per-event severity for the timeline. Falls back to action-based
    severity when a DecisionLog row (and its risk_score) isn't
    available for a given request.

    NOTE: values are lowercase ("critical"/"high"/"medium"/"low") to
    match ThreatTimeline.jsx, which uses event.severity directly as a
    CSS class name and does an exact match against the literal string
    "critical" for its highlight styling. This is a different
    vocabulary from analyzer.compute_severity() (SEVERE/HIGH/MEDIUM/
    LOW), which still feeds PeakAttack.severity elsewhere and has its
    own frontend consumer(s) — not changed here.
    """
    if risk_score is not None:
        if risk_score >= 0.8:
            return "critical"
        elif risk_score >= 0.6:
            return "high"
        elif risk_score >= 0.3:
            return "medium"
        return "low"

    return "high" if action == "block" else "medium"


class ActivityService:

    @staticmethod
    async def get_activity(client_id: int, time_window: int = 600) -> ActivityResponse:
        """
        Fetch activity data for the dashboard, backed by Postgres
        (request_logs / decision_logs) instead of Redis.
        """

        window_start = datetime.utcnow() - timedelta(seconds=time_window)

        async with AsyncSessionLocal() as db:

            # ============================================================
            # 🔹 METRICS (single aggregate query)
            # ============================================================
            metrics_row = (
                await db.execute(
                    select(
                        func.count(RequestLog.id).label("total"),
                        func.sum(
                            case((RequestLog.action == "block", 1), else_=0)
                        ).label("blocked"),
                        func.sum(
                            case((RequestLog.action == "throttle", 1), else_=0)
                        ).label("throttled"),
                        func.sum(
                            case((RequestLog.action == "allow", 1), else_=0)
                        ).label("allowed"),
                    ).where(
                        RequestLog.client_id == client_id,
                        RequestLog.created_at >= window_start,
                    )
                )
            ).one()

            total = metrics_row.total or 0
            blocked = metrics_row.blocked or 0
            throttled = metrics_row.throttled or 0
            allowed = metrics_row.allowed or 0

            # ============================================================
            # 🔹 INSIGHTS
            # ============================================================
            risk_level, risk_percent = compute_risk(blocked, total)

            attack_status = (
                "under_attack" if blocked > allowed and blocked > 50 else "stable"
            )

            insights = ActivityInsights(
                attackStatus=attack_status,
                anomalyScore=round(risk_percent, 2),
                riskLevel=risk_level,
            )

            # ============================================================
            # 🔹 METRICS (response object)
            # ============================================================
            success_rate = (allowed / total * 100) if total else 100.0

            metrics = ActivityMetrics(
                totalRequests=total,
                blockedRequests=blocked,
                throttledRequests=throttled,
                successRate=round(success_rate, 2),
            )

            health_score = round(success_rate, 2)

            # ============================================================
            # 🔹 ENDPOINTS + PATTERNS + TOP ENDPOINT
            # ============================================================
            endpoint_rows = (
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
                        RequestLog.created_at >= window_start,
                    )
                    .group_by(RequestLog.endpoint)
                    .order_by(func.count(RequestLog.id).desc())
                    .limit(10)
                )
            ).all()

            endpoints: List[EndpointActivity] = []
            patterns: List[AttackPattern] = []
            top_endpoint_data: Optional[TopEndpoint] = None

            for i, row in enumerate(endpoint_rows):
                percentage = (row.requests / total * 100) if total else 0
                ep_blocked = row.blocked or 0
                # Exact per-endpoint block rate (Postgres has this
                # directly; the old Redis version had to estimate it
                # proportionally from the overall block rate).
                risk, _ = compute_risk(ep_blocked, row.requests)

                endpoints.append(
                    EndpointActivity(
                        endpoint=row.endpoint,
                        percentage=round(percentage, 2),
                        requests=row.requests,
                        blocked=ep_blocked,
                        risk=risk,
                    )
                )

                patterns.append(
                    AttackPattern(
                        endpoint=row.endpoint,
                        percentage=round(percentage, 2),
                    )
                )

                if i == 0:
                    top_endpoint_data = TopEndpoint(
                        endpoint=row.endpoint,
                        requests=row.requests,
                        percentage=round(percentage, 2),
                    )

            # ============================================================
            # 🔹 TREND (per-minute buckets)
            # ============================================================
            minute_bucket = func.date_trunc("minute", RequestLog.created_at).label("minute")

            trend_rows = (
                await db.execute(
                    select(
                        minute_bucket,
                        func.sum(
                            case((RequestLog.action == "allow", 1), else_=0)
                        ).label("allowed"),
                        func.sum(
                            case((RequestLog.action == "throttle", 1), else_=0)
                        ).label("throttled"),
                        func.sum(
                            case((RequestLog.action == "block", 1), else_=0)
                        ).label("blocked"),
                    )
                    .where(
                        RequestLog.client_id == client_id,
                        RequestLog.created_at >= window_start,
                    )
                    .group_by(minute_bucket)
                    .order_by(minute_bucket)
                )
            ).all()

            trend: List[DecisionTrendPoint] = [
                DecisionTrendPoint(
                    time=row.minute.strftime("%H:%M"),
                    allowed=row.allowed or 0,
                    throttled=row.throttled or 0,
                    blocked=row.blocked or 0,
                )
                for row in trend_rows
            ]

            # ============================================================
            # 🔹 PEAK ATTACK (minute with the most blocked requests)
            # ============================================================
            peak = PeakAttack(time=None, blocked=0, endpoint=None, severity=None)

            if trend_rows:
                peak_row = max(trend_rows, key=lambda r: r.blocked or 0)

                if (peak_row.blocked or 0) > 0:
                    minute_start = peak_row.minute
                    minute_end = minute_start + timedelta(minutes=1)

                    top_blocked_endpoint = (
                        await db.execute(
                            select(
                                RequestLog.endpoint,
                                func.count(RequestLog.id).label("cnt"),
                            )
                            .where(
                                RequestLog.client_id == client_id,
                                RequestLog.action == "block",
                                RequestLog.created_at >= minute_start,
                                RequestLog.created_at < minute_end,
                            )
                            .group_by(RequestLog.endpoint)
                            .order_by(func.count(RequestLog.id).desc())
                            .limit(1)
                        )
                    ).first()

                    peak = PeakAttack(
                        time=minute_start.strftime("%H:%M"),
                        blocked=peak_row.blocked,
                        endpoint=top_blocked_endpoint.endpoint if top_blocked_endpoint else None,
                        severity=compute_severity(peak_row.blocked),
                    )

            # ============================================================
            # 🔹 TIMELINE (recent block/throttle events)
            # ============================================================
            timeline_rows = (
                await db.execute(
                    select(RequestLog, DecisionLog)
                    .outerjoin(DecisionLog, DecisionLog.request_id == RequestLog.id)
                    .where(
                        RequestLog.client_id == client_id,
                        RequestLog.created_at >= window_start,
                        RequestLog.action.in_(["block", "throttle"]),
                    )
                    .order_by(RequestLog.created_at.desc())
                    .limit(20)
                )
            ).all()

            timeline: List[ThreatEvent] = []
            for req, dec in timeline_rows:
                event_label = "Request Blocked" if req.action == "block" else "Request Throttled"
                risk_score = dec.risk_score if dec else None

                timeline.append(
                    ThreatEvent(
                        time=req.created_at.strftime("%H:%M:%S"),
                        event=event_label,
                        description=(dec.reason if dec and dec.reason else f"{event_label} on {req.endpoint}"),
                        severity=_event_severity(risk_score, req.action),
                        ip=req.ip_address,
                    )
                )

            # ============================================================
            # 🔹 SPIKE CORRELATIONS
            # ============================================================
            correlations = await detect_spike_correlations(db, client_id, time_window)

            if not correlations and peak.time and peak.endpoint:
                correlations.append(
                    SpikeCorrelation(
                        peak_time=peak.time,
                        blocked=peak.blocked,
                        target=peak.endpoint,
                    )
                )

            # ============================================================
            # 🔹 FINAL RESPONSE
            # ============================================================
            return ActivityResponse(
                timeline=timeline,
                endpoints=endpoints,
                trend=trend,
                insights=insights,
                metrics=metrics,
                peak=peak,
                patterns=patterns,
                correlations=correlations,
                topEndpoint=top_endpoint_data,
                healthScore=health_score,
            )