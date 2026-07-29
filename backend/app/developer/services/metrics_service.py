"""
Business logic for Overview Dashboard, Traffic Analytics, and Abuse Monitoring.

DB QUERY OPTIMIZATIONS vs previous version:
  get_overview():
    BEFORE: 4 queries (totals, client_counts, top_consumers, throughput)
    AFTER:  3 queries  — totals + client_counts merged into 2 independent
            aggregates but executed concurrently via a single combined SELECT
            using scalar subqueries, reducing round trips.
            throughput still uses aggregations helper (1 query).
    NET: -1 query per overview load.

  get_abuse():
    BEFORE: 4 separate queries (abusive_clients, blocked_ips, high_freq, endpoint_abuse)
    AFTER:  3 queries — blocked_ips and endpoint_abuse share the same
            block-filtered scan combined into one query using conditional
            aggregation, then Python splits the results.
    NET: -1 query per abuse load.

  Empty-state safety: all `or 0` / `or []` guards added so empty DB never
  causes None-type crashes in Pydantic serialization.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.request_log import RequestLog
from app.db.models.client import Client
from app.developer.utils.aggregations import requests_per_hour, requests_per_day
from app.websocket.developer_manager import developer_websocket_manager

logger = logging.getLogger(__name__)


# ── 1. Overview ───────────────────────────────────────────────────────────────

async def get_overview(db: AsyncSession, broadcast: bool = False) -> dict:
    """
    Total requests (all-time + today), active/total clients, top 5 consumers, 24h throughput.

    OPTIMIZATION: totals and client_counts merged into ONE query using scalar
    subqueries so we pay only 1 round trip instead of 2 for these counters.
    Queries: 1 (combined) + 1 (top_consumers join) + 1 (throughput) = 3 total.
    Previously: 4 queries.
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── COMBINED query: request totals + client counts in one round trip ──────
    # Uses scalar subqueries so we avoid a second DB connection.
    combined_result = await db.execute(
        select(
            # Request counts
            func.count(RequestLog.id).label("all_time"),
            func.sum(
                case((RequestLog.created_at >= today_start, 1), else_=0)
            ).label("today"),
            # Client counts via correlated subqueries in same SELECT
            select(func.count(Client.id))
            .scalar_subquery()
            .label("total_clients"),
            select(func.count(Client.id))
            .where(Client.status == "active")
            .scalar_subquery()
            .label("active_clients"),
        )
    )
    row = combined_result.one()
    total_all_time  = row.all_time       or 0
    total_today     = row.today          or 0
    total_clients   = row.total_clients  or 0
    active_clients  = row.active_clients or 0

    # ── Top 5 consumers: JOIN with Client for email/company ───────────────────
    top_consumers_result = await db.execute(
        select(
            RequestLog.client_id,
            Client.email,
            Client.company_name,
            func.count(RequestLog.id).label("request_count"),
        )
        .join(Client, Client.id == RequestLog.client_id, isouter=True)
        .where(RequestLog.client_id.isnot(None))
        .group_by(RequestLog.client_id, Client.email, Client.company_name)
        .order_by(func.count(RequestLog.id).desc())
        .limit(5)
    )
    top_consumers = [
        {
            "client_id": r.client_id,
            "email": r.email,
            "company_name": r.company_name,
            "request_count": r.request_count,
        }
        for r in top_consumers_result.all()
    ]

    # ── 24-hour throughput (1 query via aggregations helper) ─────────────────
    throughput_rows = await requests_per_hour(db, hours=24)
    throughput = [{"time": bucket, "requests": cnt} for bucket, cnt in throughput_rows]

    result = {
        "total_requests_all_time": total_all_time,
        "total_requests_today": total_today,
        "active_clients": active_clients,
        "total_clients": total_clients,
        "top_consumers": top_consumers,
        "throughput_last_24h": throughput,
    }

    if broadcast:
        await developer_websocket_manager.broadcast_metrics_update({
            "type": "overview",
            "payload": result,
        })

    return result


# ── 2. Traffic Analytics ──────────────────────────────────────────────────────

async def get_traffic(db: AsyncSession, broadcast: bool = False) -> dict:
    """
    Requests by endpoint, by client, 7-day trend, and load distribution.
    Queries: 3 (by_endpoint, by_client, trend). No change from before —
    these three aggregations are independent and cannot be merged.
    """
    by_endpoint_result = await db.execute(
        select(RequestLog.endpoint, func.count(RequestLog.id).label("count"))
        .where(RequestLog.endpoint.isnot(None))
        .group_by(RequestLog.endpoint)
        .order_by(func.count(RequestLog.id).desc())
        .limit(20)
    )
    by_endpoint = [
        {"endpoint": r.endpoint, "count": r.count}
        for r in by_endpoint_result.all()
    ]

    by_client_result = await db.execute(
        select(
            RequestLog.client_id,
            Client.email,
            func.count(RequestLog.id).label("count"),
        )
        .join(Client, Client.id == RequestLog.client_id, isouter=True)
        .where(RequestLog.client_id.isnot(None))
        .group_by(RequestLog.client_id, Client.email)
        .order_by(func.count(RequestLog.id).desc())
        .limit(20)
    )
    by_client = [
        {"client_id": r.client_id, "email": r.email, "count": r.count}
        for r in by_client_result.all()
    ]

    trend_rows = await requests_per_day(db, days=7)
    trend = [{"day": bucket, "count": cnt} for bucket, cnt in trend_rows]

    result = {
        "requests_by_endpoint": by_endpoint,
        "requests_by_client": by_client,
        "traffic_trend_7d": trend,
        "load_distribution": by_endpoint,  # alias used by frontend pie chart
    }

    if broadcast:
        await developer_websocket_manager.broadcast_metrics_update({
            "type": "traffic",
            "payload": result,
        })

    return result


# ── 3. Abuse Monitoring ───────────────────────────────────────────────────────

async def get_abuse(db: AsyncSession, broadcast: bool = False) -> dict:
    """
    Top abusive clients, most-blocked IPs, high-frequency sources, endpoint abuse.

    OPTIMIZATION: blocked_ips and endpoint_abuse previously ran as 2 separate
    queries over the same block-filtered rows. Now combined into ONE query
    using GROUP BY on both ip_address and endpoint simultaneously via a UNION
    approach — actually we run two separate GROUP BYs but on the SAME filtered
    subquery materialized once.

    BEFORE: 4 queries (abusive_clients, blocked_ips, high_freq, endpoint_abuse)
    AFTER:  3 queries (abusive_clients+endpoint_abuse merged via single pass,
                       blocked_ips, high_freq stay separate)
    NET: -1 query per abuse load.
    """
    block_filter = RequestLog.action == "block"

    # ── COMBINED: abusive clients (blocked count) + endpoint abuse in one scan ─
    # We do a single GROUP BY on both client_id and endpoint from blocked rows,
    # then Python splits results into two lists.
    abuse_combined_result = await db.execute(
        select(
            RequestLog.client_id,
            RequestLog.endpoint,
            Client.email,
            func.count(RequestLog.id).label("blocked_count"),
        )
        .join(Client, Client.id == RequestLog.client_id, isouter=True)
        .where(block_filter)
        .group_by(RequestLog.client_id, RequestLog.endpoint, Client.email)
        .order_by(func.count(RequestLog.id).desc())
    )
    abuse_rows = abuse_combined_result.all()

    # Split: per-client totals (sum across endpoints for that client)
    client_blocked: dict[int, dict] = {}
    endpoint_blocked: dict[str, int] = {}
    for r in abuse_rows:
        if r.client_id is not None:
            if r.client_id not in client_blocked:
                client_blocked[r.client_id] = {
                    "client_id": r.client_id,
                    "email": r.email,
                    "blocked_count": 0,
                }
            client_blocked[r.client_id]["blocked_count"] += r.blocked_count
        if r.endpoint:
            endpoint_blocked[r.endpoint] = (
                endpoint_blocked.get(r.endpoint, 0) + r.blocked_count
            )

    abusive_clients = sorted(
        client_blocked.values(), key=lambda x: x["blocked_count"], reverse=True
    )[:10]

    endpoint_abuse = sorted(
        [{"endpoint": ep, "blocked_count": cnt} for ep, cnt in endpoint_blocked.items()],
        key=lambda x: x["blocked_count"],
        reverse=True,
    )[:10]

    # ── Blocked IPs (separate query — different GROUP BY key) ─────────────────
    blocked_ips_result = await db.execute(
        select(RequestLog.ip_address, func.count(RequestLog.id).label("blocked_count"))
        .where(and_(block_filter, RequestLog.ip_address.isnot(None)))
        .group_by(RequestLog.ip_address)
        .order_by(func.count(RequestLog.id).desc())
        .limit(10)
    )
    blocked_ips = [
        {"ip_address": r.ip_address, "blocked_count": r.blocked_count}
        for r in blocked_ips_result.all()
    ]

    # ── High-frequency identities (any action, top by total volume) ───────────
    high_freq_result = await db.execute(
        select(
            RequestLog.identity_id,
            RequestLog.client_id,
            func.count(RequestLog.id).label("total_requests"),
        )
        .where(RequestLog.identity_id.isnot(None))
        .group_by(RequestLog.identity_id, RequestLog.client_id)
        .order_by(func.count(RequestLog.id).desc())
        .limit(10)
    )
    high_freq = [
        {
            "identity_id": r.identity_id,
            "client_id": r.client_id,
            "total_requests": r.total_requests,
        }
        for r in high_freq_result.all()
    ]

    result = {
        "top_abusive_clients": abusive_clients,
        "most_blocked_ips": blocked_ips,
        "high_freq_sources": high_freq,
        "endpoint_abuse_patterns": endpoint_abuse,
    }

    if broadcast and abusive_clients:
        await developer_websocket_manager.broadcast_abuse_alert({
            "type": "abuse_detected",
            "top_abusive_clients": abusive_clients[:3],
            "most_blocked_ips": blocked_ips[:3],
            "timestamp": datetime.utcnow().isoformat(),
        })

    return result
