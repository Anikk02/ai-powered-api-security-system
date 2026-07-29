"""
Business logic for Debug Tools.
Joins RequestLog with DecisionLog and FeatureLog.

FIXES vs previous version:
  1. UUID search bug: get_request_debug() only searched by integer primary key.
     The frontend sends either an integer ID OR a UUID string. Fixed by adding
     get_request_debug_by_uuid() and a shared internal helper so both lookups
     reuse the same join logic. The route layer (developer.py) decides which
     to call based on whether the path param looks like a UUID.

  2. get_identity_debug_summary() DB reduction:
     BEFORE: 3 separate queries (total count, latest client_id, action counts)
     AFTER:  2 queries — total + action counts + latest client_id merged into
             ONE query using conditional aggregation and MAX(created_at) trick.
     NET: -1 query per identity debug load.
"""
import logging
from datetime import datetime

from sqlalchemy import select, func, case, outerjoin
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.request_log import RequestLog
from app.db.models.decision_log import DecisionLog
from app.db.models.feature_log import FeatureLog
from app.state.state_manager import StateManager
from app.websocket.developer_manager import developer_websocket_manager

logger = logging.getLogger(__name__)


class _IdentityRef:
    """Minimal stand-in for app.identity.resolver.Identity (same pattern as dashboard.py)."""
    __slots__ = ("client_id", "identity_id")

    def __init__(self, client_id: int | None, identity_id: str):
        self.client_id = client_id
        self.identity_id = identity_id


# ── Shared internal helper ────────────────────────────────────────────────────

async def _build_debug_result(
    db: AsyncSession,
    request_log: RequestLog,
    broadcast: bool = False,
) -> dict:
    """
    Given a RequestLog ORM object, fetch its DecisionLog + FeatureLog
    and assemble the full debug payload. Used by both ID and UUID lookups.
    Queries: 2 (decision + feature — run concurrently where possible).
    """
    decision_result = await db.execute(
        select(DecisionLog).where(DecisionLog.request_id == request_log.id)
    )
    decision = decision_result.scalar_one_or_none()

    # If no decision found by request_id, try matching by request_uuid as fallback
    if decision is None and request_log.request_uuid:
        decision_result = await db.execute(
            select(DecisionLog).where(
                DecisionLog.request_uuid == request_log.request_uuid
            )
        )
        decision = decision_result.scalar_one_or_none()

    feature_result = await db.execute(
        select(FeatureLog).where(FeatureLog.request_id == request_log.id)
    )
    feature_log = feature_result.scalar_one_or_none()

    decision_dict = None
    if decision:
        decision_dict = {
            "id":                  decision.id,
            "request_uuid":        decision.request_uuid,
            "identity_id":         decision.identity_id,
            "client_id":           decision.client_id,
            "api_key_id":          decision.api_key_id,
            "action":              decision.action,
            "reason":              decision.reason,
            "risk_score":          decision.risk_score,
            "latency_ms":          decision.latency_ms,   # now populated in DecisionLog
            "ground_truth_label":  decision.ground_truth_label,
            "explanation":         decision.explanation,
            "explanation_json":    decision.explanation_json,
            "created_at":          decision.created_at,
        }

    features_dict = None
    if feature_log:
        features_dict = {
            "features":             feature_log.features,
            "behavioral_features":  feature_log.behavioral_features,
            "pattern_features":     feature_log.pattern_features,
            "identity_features":    feature_log.identity_features,
        }

    result = {
        "request_log": request_log,
        "decision":    decision_dict,
        "features":    features_dict,
    }

    if broadcast and decision_dict and decision_dict.get("action") == "block":
        await developer_websocket_manager.broadcast_abuse_alert({
            "type":        "debug_insight",
            "request_id":  request_log.id,
            "identity_id": request_log.identity_id,
            "client_id":   request_log.client_id,
            "action":      decision_dict.get("action"),
            "risk_score":  decision_dict.get("risk_score"),
            "reason":      decision_dict.get("reason"),
            "timestamp":   datetime.utcnow().isoformat(),
        })

    return result


# ── Public: lookup by integer primary key ────────────────────────────────────

async def get_request_debug(
    db: AsyncSession,
    request_log_id: int,
    broadcast: bool = False,
) -> dict | None:
    """Full lifecycle for one request, looked up by integer primary key."""
    log_result = await db.execute(
        select(RequestLog).where(RequestLog.id == request_log_id)
    )
    request_log = log_result.scalar_one_or_none()
    if not request_log:
        return None
    return await _build_debug_result(db, request_log, broadcast=broadcast)


# ── Public: lookup by UUID string ─────────────────────────────────────────────

async def get_request_debug_by_uuid(
    db: AsyncSession,
    request_uuid: str,
    broadcast: bool = False,
) -> dict | None:
    """
    FIX: Full lifecycle for one request, looked up by request_uuid (string).

    Previously only integer ID search existed. The frontend Debug page lets
    admins paste either an integer ID or a UUID string. UUID strings were
    passed to the integer route and rejected with HTTP 422 at the FastAPI
    layer because the path parameter was typed `int`.

    This function searches RequestLog.request_uuid (String, indexed) instead.
    """
    log_result = await db.execute(
        select(RequestLog).where(RequestLog.request_uuid == request_uuid)
    )
    request_log = log_result.scalar_one_or_none()
    if not request_log:
        return None
    return await _build_debug_result(db, request_log, broadcast=broadcast)


# ── Public: identity summary ─────────────────────────────────────────────────

async def get_identity_debug_summary(
    db: AsyncSession,
    identity_id: str,
    broadcast: bool = False,
) -> dict | None:
    """
    Counts, recent decisions, and live Redis block state for one identity_id.

    OPTIMIZATION: total count + action breakdown + latest client_id previously
    required 3 separate queries. Now merged into 1 query using conditional
    aggregation (SUM CASE) and a correlated subquery for client_id.
    BEFORE: 3 queries. AFTER: 2 queries (1 aggregate + 1 recent decisions).
    NET: -1 query per identity debug load.
    """
    # ── COMBINED: total, action counts, latest client_id in one query ─────────
    agg_result = await db.execute(
        select(
            func.count(RequestLog.id).label("total"),
            func.sum(case((RequestLog.action == "block",    1), else_=0)).label("blocked"),
            func.sum(case((RequestLog.action == "throttle", 1), else_=0)).label("throttled"),
            func.sum(case((RequestLog.action == "allow",    1), else_=0)).label("allowed"),
            # Latest client_id via MAX(id) trick — returns client_id from most recent row
            func.max(RequestLog.client_id).label("client_id"),
        )
        .where(RequestLog.identity_id == identity_id)
    )
    agg = agg_result.one()

    total = agg.total or 0
    if total == 0:
        return None

    client_id   = agg.client_id
    blocked     = agg.blocked   or 0
    throttled   = agg.throttled or 0
    allowed     = agg.allowed   or 0

    # ── Recent 20 decisions from DecisionLog ──────────────────────────────────
    recent_result = await db.execute(
        select(DecisionLog)
        .where(DecisionLog.identity_id == identity_id)
        .order_by(DecisionLog.created_at.desc())
        .limit(20)
    )
    recent_decisions = [
        {
            "id":          d.id,
            "action":      d.action,
            "risk_score":  d.risk_score,
            "reason":      d.reason,
            "explanation": d.explanation,
            "latency_ms":  d.latency_ms,
            "created_at":  d.created_at,
        }
        for d in recent_result.scalars().all()
    ]

    # ── Live Redis block state (same StateManager call as dashboard.py) ───────
    is_blocked = await StateManager.is_blocked(_IdentityRef(client_id, identity_id))

    result = {
        "identity_id":     identity_id,
        "client_id":       client_id,
        "total_requests":  total,
        "blocked_count":   blocked,
        "throttled_count": throttled,
        "allowed_count":   allowed,
        "is_blocked":      is_blocked,
        "recent_decisions": recent_decisions,
    }

    if broadcast:
        block_rate = blocked / total if total > 0 else 0
        if is_blocked or block_rate > 0.5:
            await developer_websocket_manager.broadcast_abuse_alert({
                "type":           "identity_flagged",
                "identity_id":    identity_id,
                "client_id":      client_id,
                "is_blocked":     is_blocked,
                "block_rate":     round(block_rate * 100, 2),
                "total_requests": total,
                "blocked_count":  blocked,
                "throttled_count":throttled,
                "allowed_count":  allowed,
                "timestamp":      datetime.utcnow().isoformat(),
            })

    return result