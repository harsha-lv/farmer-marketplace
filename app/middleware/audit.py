"""Audit logging middleware recording all mutating API operations."""

import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.auth.rate_limiter import get_client_ip
from app.auth.repository import AuthRepository

logger = logging.getLogger("app.middleware.audit")

MUTATING_METHODS = frozenset(["POST", "PUT", "PATCH", "DELETE"])


def extract_resource_info(path: str) -> tuple[str | None, str | None]:
    """Derive resource type and resource ID from the URL path.

    Example: /api/v1/farmers/123 -> ("farmer", "123")
    Example: /api/v1/lots/LOT-456/assay -> ("lot", "LOT-456")
    """
    segments = [s for s in path.strip("/").split("/") if s and s not in ("api", "v1")]
    if not segments:
        return None, None

    resource_type = segments[0].rstrip("s")  # "farmers" -> "farmer"
    resource_id = segments[1] if len(segments) > 1 and not segments[1].startswith("?") else None
    return resource_type, resource_id


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware that logs mutating operations (POST, PUT, PATCH, DELETE) to the audit_log table."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Only audit mutating operations on successful or client-side responses (exclude 5xx server faults)
        if request.method in MUTATING_METHODS and response.status_code < 500:
            path = request.url.path
            # Skip health probes or internal metrics
            if path in ("/health", "/ready", "/healthz"):
                return response

            actor_id: str | None = None
            actor_type: str = "anonymous"

            # Check if user context exists on request state
            current_user = getattr(request.state, "current_user", None)
            current_api_client = getattr(request.state, "current_api_client", None)

            if current_user:
                if current_user.is_api_client:
                    actor_id = current_user.client_id
                    actor_type = "api_client"
                else:
                    actor_id = str(current_user.user_id) if current_user.user_id else None
                    actor_type = "user"
            elif current_api_client:
                actor_id = current_api_client.client_id
                actor_type = "api_client"

            consent_artifact_id = (
                request.headers.get("x-consent-artifact-id")
                or getattr(request.state, "consent_artifact_id", None)
            )

            resource_type, resource_id = extract_resource_info(path)
            ip = get_client_ip(request)
            user_agent = request.headers.get("user-agent")
            request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")

            # Asynchronously write to audit_log if database is available in app state
            db = getattr(request.app.state, "database", None)
            if db:
                try:
                    async with db.session_factory() as session:
                        repo = AuthRepository(session)
                        await repo.write_audit_log(
                            actor_id=actor_id,
                            actor_type=actor_type,
                            action=f"{request.method} {path}",
                            resource_type=resource_type,
                            resource_id=resource_id,
                            consent_artifact_id=consent_artifact_id,
                            ip=ip,
                            user_agent=user_agent,
                            request_id=request_id,
                            details={"status_code": response.status_code},
                        )
                        await session.commit()
                except Exception as exc:
                    logger.warning("Failed to write to audit_log: %s", exc)

        return response
