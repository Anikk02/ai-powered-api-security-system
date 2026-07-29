"""
Business logic for the Global Logs module.
Paginated, filterable read across ALL clients' RequestLog rows.

FIXES vs previous version:
  1. risk_score field: RequestLog has no risk_score column. The frontend
     requires it. Fixed by LEFT JOIN to DecisionLog on request_uuid so
     risk_score is fetched in the same query — no extra round trip.

  2. Broadcast bug removed: previous code broadcast only when len(logs)==1
     which was never correct for a paginated list endpoint. Broadcast is
     removed from the list function entirely (real-time log push happens
     in the middleware when a request is processed, not in the read path).

  3. Query count stays at 2 (count + paginated rows) — unchanged.
"""
import logging
import math
from datetime import datetime

from sqlalchemy import select, func, outerjoin
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.request_log import RequestLog
from app.db.models.decision_log import DecisionLog
from app.developer.utils.filters import apply_request_log_filters

logger = logging.getLogger(__name__)


async def get_logs(
    db: AsyncSession,
    client_id: int | None = None,
    identity_id: str | None = None,
    ip_address: str | None = None,
    endpoint: str | None = None,
    action: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
    broadcast: bool = False,   # kept in signature for backward compat, no longer used
) -> dict:
    """
    Return one page of RequestLog rows with risk_score joined from DecisionLog.

    OPTIMIZATION: risk_score is fetched via a single LEFT JOIN on
    request_uuid in the same SELECT — no second query per row.

    DB queries: 2 (count subquery + paginated rows with join).
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 200:
        page_size = 50

    # ── Base query: RequestLog LEFT JOIN DecisionLog on request_uuid ──────────
    # We join on request_uuid (both String columns) because DecisionLog does
    # not have a direct FK to request_logs.id in all cases, but always carries
    # the same request_uuid that was assigned at middleware entry.
    base_query = (
        select(
            RequestLog.id,
            RequestLog.request_uuid,
            RequestLog.client_id,
            RequestLog.identity_id,
            RequestLog.api_key_id,
            RequestLog.endpoint,
            RequestLog.method,
            RequestLog.ip_address,
            RequestLog.user_agent,
            RequestLog.status_code,
            RequestLog.action,
            RequestLog.created_at,
            # risk_score pulled from DecisionLog — None when no decision exists
            DecisionLog.risk_score.label("risk_score"),
        )
        .select_from(
            outerjoin(
                RequestLog,
                DecisionLog,
                RequestLog.request_uuid == DecisionLog.request_uuid,
            )
        )
    )

    # ── Apply filters (on RequestLog columns only) ────────────────────────────
    base_query = apply_request_log_filters(
        base_query,
        client_id=client_id,
        identity_id=identity_id,
        ip_address=ip_address,
        endpoint=endpoint,
        action=action,
        start_time=start_time,
        end_time=end_time,
    )

    # ── Count total matching rows (uses subquery — 1 DB call) ─────────────────
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    # ── Fetch page (1 DB call) ────────────────────────────────────────────────
    offset = (page - 1) * page_size
    rows_result = await db.execute(
        base_query
        .order_by(RequestLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = rows_result.mappings().all()

    # ── Serialize to plain dicts (schema handles validation) ─────────────────
    logs = [
        {
            "id":           r["id"],
            "request_uuid": r["request_uuid"],
            "client_id":    r["client_id"],
            "identity_id":  r["identity_id"],
            "api_key_id":   r["api_key_id"],
            "endpoint":     r["endpoint"],
            "method":       r["method"],
            "ip_address":   r["ip_address"],
            "user_agent":   r["user_agent"],
            "status_code":  r["status_code"],
            "action":       r["action"],
            "risk_score":   r["risk_score"],   # ← now populated from DecisionLog
            "created_at":   r["created_at"],
        }
        for r in rows
    ]

    return {
        "total":       total,
        "page":        page,
        "page_size":   page_size,
        "total_pages": total_pages,
        "logs":        logs,
    }
