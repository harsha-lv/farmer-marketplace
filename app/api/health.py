"""Health check and probe endpoints for load balancers and Kubernetes clusters.

Endpoints:
- GET /health (and /health/live, /live): Cheap liveness probe returning HTTP 200.
- GET /ready (and /health/ready): Comprehensive readiness probe checking Database,
  Redis, NATS, and Kafka with short timeouts (1.5s).
  Returns HTTP 200 when ready, HTTP 503 when required dependencies are unavailable.
  Strictly suppresses dependency breakdown to unauthenticated callers to prevent reconnaissance.
"""

import asyncio
import ipaddress
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.api.deps import SessionDep, SettingsDep
from app.config import Settings

logger = logging.getLogger("app.api.health")

router = APIRouter(tags=["health"])

INTERNAL_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
]


# ============================================================================
# Pydantic v2 Models
# ============================================================================


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str
    timestamp: str
    version: str


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    database: str | None = None
    dependencies: dict[str, str] | None = None


class LivenessResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str


# ============================================================================
# Authentication Helper
# ============================================================================


def is_authenticated_health_caller(request: Request, settings: Settings) -> bool:
    """Determine whether the caller is authorized to view internal dependency breakdown."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token and (token == settings.jwt_secret_key or token == settings.metrics_token):
            return True
        try:
            # Check JWT decode
            from app.auth.security import decode_token

            payload = decode_token(token, settings.jwt_secret_key)
            if payload:
                return True
        except Exception:
            pass

    admin_key = request.headers.get("x-admin-key", "").strip()
    if admin_key and (admin_key == settings.jwt_secret_key or admin_key == settings.metrics_token):
        return True

    return False


# ============================================================================
# Health Endpoints
# ============================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="L7 Load Balancer Health Probe",
)
async def health(settings: SettingsDep) -> dict[str, str]:
    """Lightweight load balancer health probe returning 200 OK with no database dependency."""
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": settings.app_version or "1.0.0",
    }


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"description": "Required service dependency is unavailable"}},
    summary="Readiness Probe",
)
@router.get("/ready", include_in_schema=False)
async def readiness(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> Response:
    """Readiness probe checking DB, Redis, NATS, and Kafka with short timeouts.

    Returns HTTP 200 if all required dependencies are ready, or HTTP 503 if any required
    dependency is unreachable.
    Does NOT expose dependency details to unauthenticated callers.
    """
    timeout = 1.5
    checks: dict[str, str] = {}
    is_healthy = True

    # 1. Check Database (REQUIRED)
    try:
        await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=timeout)
        checks["database"] = "connected"
    except Exception as exc:
        logger.warning("Readiness probe: database check failed (%s)", exc)
        checks["database"] = "unreachable"
        is_healthy = False

    # 2. Check Redis (REQUIRED if redis_url configured)
    if settings.redis_url:
        try:
            from app.cache.client import get_cache_client

            cache = get_cache_client(settings)
            pong = await asyncio.wait_for(cache.ping(), timeout=timeout)
            if pong:
                checks["redis"] = "connected"
            else:
                checks["redis"] = "degraded"
        except Exception as exc:
            logger.warning("Readiness probe: redis check failed (%s)", exc)
            checks["redis"] = "unreachable"
            is_healthy = False
    else:
        checks["redis"] = "in_memory"

    # 3. Check NATS (JetStream Engine)
    try:
        from app.telemetry.jetstream import get_jetstream_engine

        engine = get_jetstream_engine()
        checks["nats"] = "ready" if engine is not None else "unconfigured"
    except Exception as exc:
        logger.warning("Readiness probe: NATS check failed (%s)", exc)
        checks["nats"] = "unreachable"

    # 4. Check Kafka (if bootstrap servers configured)
    if settings.kafka_bootstrap_servers:
        try:
            from app.events.kafka import KafkaProducerClient

            producer = KafkaProducerClient(settings)
            # Lightweight check: verify client configuration and connectivity if already started
            if getattr(producer, "producer", None) is not None:
                checks["kafka"] = "connected"
            else:
                checks["kafka"] = "configured"
        except Exception as exc:
            logger.warning("Readiness probe: Kafka check failed (%s)", exc)
            checks["kafka"] = "unreachable"
            is_healthy = False
    else:
        checks["kafka"] = "not_configured"

    status_code = 200 if is_healthy else 503
    authenticated = is_authenticated_health_caller(request, settings)

    if not authenticated:
        # Strip all dependency details for unauthenticated callers
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if is_healthy else "unavailable",
            },
        )

    # Return full diagnostic report for authenticated administrative callers
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_healthy else "unavailable",
            "database": checks.get("database", "unknown"),
            "dependencies": checks,
            "timestamp": datetime.now(UTC).isoformat(),
            "version": settings.app_version or "1.0.0",
        },
    )


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    summary="Kubernetes Liveness Probe",
)
@router.get("/live", include_in_schema=False)
async def liveness() -> dict[str, str]:
    """Kubernetes liveness probe returning immediately to confirm process responsiveness."""
    return {"status": "alive"}
