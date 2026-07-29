"""
Developer Control Panel routes.

FIX vs previous version:
  UUID debug endpoint added: the previous /debug/request/{request_log_id}
  only accepted integer IDs. The frontend also sends UUID strings. A new
  route /debug/request/uuid/{request_uuid} handles string UUIDs. The
  existing integer route is UNCHANGED for backward compatibility.

All other routes, prefixes, auth, and response_models are identical to
the original file.
"""
import logging
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.authentication.admin_dependencies import get_current_admin
from app.db.models.admin import Admin

from app.developer.services import (
    metrics_service,
    logs_service,
    clients_service,
    system_service,
    debug_service,
)
from app.developer.schemas.metrics import OverviewResponse, TrafficResponse, AbuseResponse
from app.developer.schemas.logs import GlobalLogsResponse
from app.developer.schemas.clients import DeveloperClientsResponse, DeveloperClientInfo, ClientStatusUpdate
from app.developer.schemas.system import SystemHealthResponse
from app.developer.schemas.debug import DebugRequestInfo, DebugIdentitySummary
from app.websocket.developer_manager import developer_websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/developer", tags=["Developer Panel"])


# ─────────────────────────────────────────────────────────────────────────────
# 1. OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Total requests (all-time/today), active clients, top 5 consumers, 24h throughput."""
    return await metrics_service.get_overview(db)


# ─────────────────────────────────────────────────────────────────────────────
# 2. TRAFFIC ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/traffic", response_model=TrafficResponse)
async def get_traffic(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Requests by endpoint, by client, 7-day trend, load distribution."""
    return await metrics_service.get_traffic(db)


# ─────────────────────────────────────────────────────────────────────────────
# 3. ABUSE MONITORING
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/abuse", response_model=AbuseResponse)
async def get_abuse(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Top abusive clients, most-blocked IPs, high-frequency sources, endpoint abuse patterns."""
    return await metrics_service.get_abuse(db)


# ─────────────────────────────────────────────────────────────────────────────
# 4. GLOBAL LOGS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/logs", response_model=GlobalLogsResponse)
async def get_logs(
    current_admin: Admin = Depends(get_current_admin),
    client_id:   Optional[int]      = Query(None, description="Filter by client ID"),
    identity_id: Optional[str]      = Query(None, description="Filter by identity ID"),
    ip_address:  Optional[str]      = Query(None, description="Filter by IP address"),
    endpoint:    Optional[str]      = Query(None, description="Filter by endpoint path"),
    action:      Optional[str]      = Query(None, description="allow | throttle | block"),
    start_time:  Optional[datetime] = Query(None, description="ISO-8601 start datetime"),
    end_time:    Optional[datetime] = Query(None, description="ISO-8601 end datetime"),
    page:        int                = Query(1,  ge=1),
    page_size:   int                = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Centralized, filterable, paginated log view across ALL clients."""
    return await logs_service.get_logs(
        db,
        client_id=client_id,
        identity_id=identity_id,
        ip_address=ip_address,
        endpoint=endpoint,
        action=action,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. CLIENT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/clients", response_model=DeveloperClientsResponse)
async def get_all_clients(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """View all registered clients with usage stats and API key info."""
    return await clients_service.get_all_clients(db)


@router.get("/clients/{client_id}", response_model=DeveloperClientInfo)
async def get_client(
    client_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Single client lookup."""
    client = await clients_service.get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/clients/{client_id}/status")
async def update_client_status(
    client_id: int,
    payload: ClientStatusUpdate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Activate / deactivate / suspend / lock a client.
    Body: { "status": "active" | "inactive" | "suspended" | "locked" }
    """
    try:
        result = await clients_service.set_client_status(db, client_id, payload.status)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not result:
        raise HTTPException(status_code=404, detail="Client not found")
    return result


@router.post("/api-keys/{api_key_id}/revoke")
async def revoke_api_key(
    api_key_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Revoke any client's API key (deactivates, preserves audit trail)."""
    result = await clients_service.revoke_api_key(db, api_key_id)
    if not result:
        raise HTTPException(status_code=404, detail="API key not found")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 6. SYSTEM HEALTH
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/system", response_model=SystemHealthResponse)
async def get_system_health(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """API latency, error rate, DB status, Redis/cache status, latency trend."""
    return await system_service.get_system_health(db)


# ─────────────────────────────────────────────────────────────────────────────
# 7. DEBUG TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/debug/request/{request_log_id}", response_model=DebugRequestInfo)
async def debug_request(
    request_log_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Inspect one request's full lifecycle by integer primary key ID."""
    info = await debug_service.get_request_debug(db, request_log_id)
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"Request log ID {request_log_id} not found",
        )
    return info


@router.get("/debug/request/uuid/{request_uuid}", response_model=DebugRequestInfo)
async def debug_request_by_uuid(
    request_uuid: str,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    FIX: Inspect one request's full lifecycle by UUID string.

    Previously only the integer ID route existed. The frontend Debug page
    lets admins paste a UUID (e.g. "a1b2c3d4-...") — that was rejected with
    HTTP 422 because FastAPI tried to coerce the string to int.
    This new route accepts the UUID as a plain string path parameter.
    """
    info = await debug_service.get_request_debug_by_uuid(db, request_uuid)
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"Request UUID '{request_uuid}' not found",
        )
    return info


@router.get("/debug/identity/{identity_id}", response_model=DebugIdentitySummary)
async def debug_identity(
    identity_id: str,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Inspect one identity's decision history and live Redis block state."""
    summary = await debug_service.get_identity_debug_summary(db, identity_id)
    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No logs found for identity '{identity_id}'",
        )
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# 8. WEBSOCKET FOR REAL-TIME UPDATES
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def developer_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time developer panel updates.
    Message types: system_health_update, new_log, abuse_alert,
                   metrics_update, client_update.
    """
    await developer_websocket_manager.connect(websocket)

    try:
        await websocket.send_json({
            "type":          "connection_established",
            "message":       "Connected to Developer Panel WebSocket",
            "connection_id": developer_websocket_manager.connection_counter,
        })

        while True:
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({
                    "type":      "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                })
            else:
                try:
                    message = json.loads(data)
                    await websocket.send_json({
                        "type":    "ack",
                        "message": f"Received: {message.get('action', 'unknown')}",
                    })
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type":    "error",
                        "message": "Invalid JSON format",
                    })

    except WebSocketDisconnect:
        developer_websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        developer_websocket_manager.disconnect(websocket)
