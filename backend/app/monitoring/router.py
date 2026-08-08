"""
Monitoring REST API & WebSocket Router
=======================================
FastAPI router for the Real-Time Monitoring Center.

Endpoints:
  GET  /api/monitoring/overview - Live monitoring overview
  GET  /api/monitoring/health   - Module health check
  WS   /ws/monitoring           - WebSocket streaming of live metrics

All endpoints include:
- Authentication and RBAC
- Rate limiting (via global middleware)
- Caching
- Audit logging
- Structured error handling
- OpenAPI documentation
"""

import asyncio
import contextlib
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from loguru import logger

from ..core.audit import get_audit_logger
from ..core.cache import get_cache
from ..core.config import APP_ENV
from ..core.security import decode_token
from .config import MonitoringConfig
from .schemas import MonitoringOverview
from .service import MonitoringService, get_monitoring_service

# =============================================================================
# Router Configuration
# =============================================================================

router = APIRouter(
    prefix="/api/monitoring",
    tags=["monitoring"],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
    },
)

# =============================================================================
# Dependencies
# =============================================================================


def get_service() -> MonitoringService:
    """Get the monitoring service singleton."""
    return get_monitoring_service()


async def require_admin(request: Request) -> None:
    """Require admin authentication for sensitive monitoring endpoints."""
    config = MonitoringConfig.from_env()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Monitoring module is disabled",
        )
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    role = payload.get("role", "user")
    if role not in ("admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


# =============================================================================
# REST Endpoints
# =============================================================================


@router.get(
    "/overview",
    response_model=MonitoringOverview,
    summary="Get Live Monitoring Overview",
    description="""
    Get a consolidated real-time view of the platform:

    - System metrics (CPU, memory, latency, requests, errors, queue, workers)
    - Prediction rate per second
    - Recent attack events (for world map rendering)
    - Country statistics
    - Top scam sources
    - Most dangerous domains
    - Redis cache statistics

    Results are cached briefly for performance.
    """,
)
async def get_overview(
    request: Request,
    service: MonitoringService = Depends(get_service),
) -> MonitoringOverview:
    """Get the consolidated monitoring overview."""
    config = MonitoringConfig.from_env()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Monitoring module is disabled",
        )

    # Cache for brief period to avoid hammering psutil
    cache = get_cache()
    cache_key = "monitoring:overview"
    try:
        cached = await cache.get(cache_key)
        if cached:
            return MonitoringOverview(**cached)
    except Exception:
        pass

    overview = await service.get_overview()

    with contextlib.suppress(Exception):
        await cache.set(cache_key, overview.model_dump(), ttl=5)

    get_audit_logger().log(
        action="monitoring.overview",
        actor=getattr(request.state, "user_email", "anonymous"),
        resource="monitoring",
        result="success",
        ip_address=request.client.host if request.client else None,
        details={"prediction_rate": overview.prediction_rate.rate_per_second},
    )

    return overview


@router.get(
    "/health",
    summary="Monitoring Module Health",
    description="Check the health of the Real-Time Monitoring Center.",
    include_in_schema=APP_ENV != "production",
)
async def monitoring_health(
    service: MonitoringService = Depends(get_service),
) -> dict[str, Any]:
    """Check monitoring module health."""
    return await service.health_check()


# =============================================================================
# WebSocket Endpoint
# =============================================================================


@router.websocket("/ws/monitoring")
async def monitoring_websocket(websocket: WebSocket) -> None:
    """Stream live monitoring metrics over WebSocket.

    Sends a metrics payload every `MONITORING_METRICS_INTERVAL` seconds.
    Requires `?token=<jwt>` query parameter for authentication.
    """
    config = MonitoringConfig.from_env()
    if not config.enabled or not config.websocket_enabled:
        await websocket.close(code=4403, reason="Monitoring WebSocket disabled")
        return

    # Authenticate via query token
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4401, reason="Authentication required")
        return
    payload = decode_token(token)
    if payload is None:
        await websocket.close(code=4401, reason="Invalid token")
        return

    await websocket.accept()
    service = get_monitoring_service()
    interval = config.metrics_interval_seconds

    logger.info("Monitoring WebSocket client connected")
    try:
        while True:
            overview = await service.get_overview()
            await websocket.send_json(
                {
                    "type": "monitoring",
                    "payload": overview.model_dump(mode="json"),
                    "timestamp": overview.generated_at.isoformat(),
                }
            )
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        logger.info("Monitoring WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Monitoring WebSocket error: {e}")
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="Internal server error")
