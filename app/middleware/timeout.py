"""Server-side request timeout middleware.

Enforces strict per-request execution timeouts driven by settings.server_request_timeout_seconds.
If a request exceeds the configured threshold, cancels execution and returns an RFC 7807
504 Gateway Timeout problem document without leaking internal stack traces.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.exceptions import make_problem_response

logger = logging.getLogger("app.middleware.timeout")


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing server-side execution timeout on HTTP requests."""

    def __init__(self, app: Any, timeout_seconds: float | None = None) -> None:
        super().__init__(app)
        settings = get_settings()
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else getattr(settings, "server_request_timeout_seconds", 30.0)
        )

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # Exclude long-running telemetry / streaming routes if any
        if request.url.path.startswith("/api/v1/telemetry/ws"):
            return await call_next(request)

        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await call_next(request)
        except TimeoutError:
            path = request.url.path
            method = request.method
            logger.warning("Request timed out after %.2fs: %s %s", self.timeout_seconds, method, path)
            return make_problem_response(
                status_code=504,
                title="Gateway Timeout",
                detail=f"The server timed out waiting for request '{method} {path}' to complete (limit: {self.timeout_seconds}s).",
                code="GATEWAY_TIMEOUT",
                request=request,
            )
