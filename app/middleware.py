"""Application middleware: CORS configuration, Request ID tracing, and Structured JSON Logging."""

import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.logging_config import request_id_ctx

# Default allowed origins including local development ports and Android emulator host alias (10.0.2.2)
DEFAULT_CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://10.0.2.2:8080",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]


def configure_cors(
    app: FastAPI,
    allowed_origins: list[str] | None = None,
) -> None:
    """Configure CORSMiddleware on the FastAPI application instance.

    - CORS allowlist driven by settings/env (never wildcard '*' with credentials)
    - Allows credentials = True
    - Exposes security & tracing headers
    """
    if allowed_origins is None:
        from app.config import get_settings
        settings = getattr(app.state, "settings", None) or get_settings()
        _cors_str = getattr(settings, "cors_origins", None)
        if _cors_str:
            allowed_origins = [o.strip() for o in _cors_str.split(",") if o.strip()]
        else:
            allowed_origins = list(DEFAULT_CORS_ORIGINS)

    # Never wildcard with credentials
    filtered_origins = [o for o in allowed_origins if o != "*"]
    if not filtered_origins:
        filtered_origins = list(DEFAULT_CORS_ORIGINS)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=filtered_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=[
            "*",
            "Authorization",
            "X-API-Key",
            "X-XSRF-Token",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-ID",
            "X-Consent-Artifact-Id",
            "X-Farmer-Id",
        ],
        expose_headers=[
            "Authorization",
            "X-API-Key",
            "X-XSRF-Token",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-ID",
            "X-Consent-Artifact-Id",
            "X-Farmer-Id",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ],
    )



class RequestIDMiddleware:
    """Pure ASGI middleware that ensures every HTTP request has an X-Request-ID.

    - Generates a UUID4 for every incoming request if no X-Request-ID header is present.
    - Attaches it to the request state as request.state.request_id.
    - Adds it to the response headers as X-Request-ID.
    - Uses Python contextvars (request_id_ctx) for access in logging throughout the request lifecycle.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check for existing X-Request-ID header (case-insensitive in ASGI scope)
        request_id: str | None = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"x-request-id":
                request_id = value.decode("utf-8", errors="ignore").strip()
                break

        if not request_id:
            request_id = str(uuid.uuid4())

        # Bind to contextvars
        token = request_id_ctx.set(request_id)

        # Attach to request state
        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_ctx.reset(token)


from app.logging_config import (
    JSONLogFormatter,
    PIIRedactionFilter,
    redact_pii,
    setup_structured_logging,
)

__all__ = [
    "DEFAULT_CORS_ORIGINS",
    "JSONLogFormatter",
    "PIIRedactionFilter",
    "RequestIDMiddleware",
    "configure_cors",
    "redact_pii",
    "request_id_ctx",
    "setup_structured_logging",
]

