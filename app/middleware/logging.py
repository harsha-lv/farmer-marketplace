"""Structured JSON request/response logging middleware using Python's logging module.

Logs:
- request_id (UUID) injected into response as X-Request-Id
- method, path, status_code, duration_ms, client_ip, user_agent
- Masks sensitive data (passwords, tokens, keys) and never logs request bodies for auth endpoints.
"""

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.middleware.logging")

AUTH_PATH_KEYWORDS = frozenset([
    "auth",
    "login",
    "token",
    "password",
    "consents",
    "agristack",
])

SENSITIVE_FIELD_PATTERNS = frozenset([
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "authorization",
    "aadhar",
    "aadhaar",
    "private_key",
    "signature",
    "client_secret",
    "credential",
])


def is_auth_path(path: str) -> bool:
    """Return True if the endpoint URL path corresponds to an authentication,

    consent, or identity verification route.
    """
    path_lower = path.lower()
    return any(keyword in path_lower for keyword in AUTH_PATH_KEYWORDS)


def mask_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive values (passwords, tokens, secrets) in structured payloads."""
    if isinstance(data, dict):
        masked: dict[str, Any] = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if any(pattern in key_lower for pattern in SENSITIVE_FIELD_PATTERNS):
                masked[key] = "***REDACTED***"
            elif isinstance(value, (dict, list)):
                masked[key] = mask_sensitive_data(value)
            else:
                masked[key] = value
        return masked
    elif isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    return data


def extract_client_ip(request: Request) -> str:
    """Extract authoritative client IP address honoring X-Forwarded-For and X-Real-IP headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Production-grade structured JSON logging middleware.

    Emits structured JSON logs containing request metadata, execution duration,
    client identifiers, and status codes while redacting sensitive authentication payloads.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract or mint unique request_id
        incoming_req_id = request.headers.get("x-request-id")
        request_id = incoming_req_id.strip() if incoming_req_id else str(uuid.uuid4())
        request.state.request_id = request_id

        client_ip = extract_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        path = request.url.path
        method = request.method

        # Body logging policy: Strictly DO NOT log request bodies for auth endpoints
        body_logged: Any = None
        if is_auth_path(path):
            body_logged = "[REDACTED_AUTH_ENDPOINT]"
        elif method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "").lower()
            content_length = request.headers.get("content-length")
            # Only inspect small JSON payloads (< 64KB) to avoid memory overhead
            if content_length and int(content_length) > 0 and int(content_length) < 65536:
                if "application/json" in content_type:
                    try:
                        raw_body = await request.body()
                        if raw_body:
                            parsed = json.loads(raw_body.decode("utf-8"))
                            body_logged = mask_sensitive_data(parsed)
                    except Exception:
                        body_logged = "[UNPARSEABLE_BODY]"

        from app.logging_config import get_otel_trace_and_span_id, sanitize_object

        trace_id, span_id = get_otel_trace_and_span_id()

        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log_record = {
                "timestamp": datetime.now(UTC).isoformat(),
                "request_id": request_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "method": method,
                "path": path,
                "status_code": 500,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "error": str(exc),
            }
            if body_logged is not None:
                log_record["request_body"] = sanitize_object(body_logged)
            logger.error(json.dumps(log_record))
            raise
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log_record = {
                "timestamp": datetime.now(UTC).isoformat(),
                "request_id": request_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
                "user_agent": user_agent,
            }
            if body_logged is not None:
                log_record["request_body"] = sanitize_object(body_logged)

            if status_code >= 500:
                logger.error(json.dumps(log_record))
            elif status_code >= 400:
                logger.warning(json.dumps(log_record))
            else:
                logger.info(json.dumps(log_record))

