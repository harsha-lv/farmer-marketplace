"""Production-grade security middleware for FastAPI.

Implements:
1. CORS configuration tailored for Kotlin Android frontend (and web clients).
2. Rate limiting using SlowAPI (100 req/min general, 20 req/min auth, 500 req/min price data).
3. Security headers (X-Content-Type-Options, X-Frame-Options, HSTS, X-XSS-Protection, CSP).
4. Request size limiting (max 10MB body).
"""

import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from limits import parse
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("app.middleware.security")

# 10 MB maximum request payload size
MAX_REQUEST_BODY_SIZE: int = 10 * 1024 * 1024

# SlowAPI Rate Limit definitions
GENERAL_LIMIT = parse("100/minute")
AUTH_LIMIT = parse("20/minute")
PRICE_LIMIT = parse("500/minute")

AUTH_PATH_KEYWORDS = frozenset([
    "auth",
    "login",
    "token",
    "password",
    "consents",
    "agristack",
])

PRICE_PATH_KEYWORDS = frozenset([
    "prices",
    "mandi",
    "rollups",
    "volatility",
    "forecast",
])

def _create_limiter() -> Limiter:
    try:
        from app.config import get_settings
        settings = get_settings()
        if settings.redis_url and settings.cache_enabled:
            return Limiter(
                key_func=get_remote_address,
                storage_uri=settings.redis_url,
                storage_options={"key_prefix": "ratelimit"},
                strategy="fixed-window",
            )
    except Exception:
        logger.critical("Rate limiter Redis unavailable — falling back to in-memory. Limits are per-process only!")
        return Limiter(
            key_func=get_remote_address,
            storage_uri="memory://",
            strategy="fixed-window",
        )
    logger.critical("Rate limiter Redis unavailable — falling back to in-memory. Limits are per-process only!")
    return Limiter(
        key_func=get_remote_address,
        storage_uri="memory://",
        strategy="fixed-window",
    )


# Global slowapi Limiter instance backed by Redis (or memory fallback)
limiter = _create_limiter()


def get_cors_origins() -> list[str]:
    """Retrieve allowed CORS origins from settings (APP_CORS_ORIGINS / CORS_ORIGINS).

    Defaults to '*' for local and development environments.
    """
    from app.config import get_settings
    cors_str = get_settings().cors_origins.strip()
    if not cors_str or cors_str == "*":
        return ["*"]
    return [origin.strip() for origin in cors_str.split(",") if origin.strip()]


def configure_cors(app: FastAPI, origins: list[str] | None = None) -> None:
    """Configure CORS middleware allowing Kotlin Android frontend clients.

    Allows credentials, all methods, and headers including:
    X-Consent-Artifact-Id, X-Farmer-Id, Authorization, and X-Request-Id.
    """
    allowed_origins = origins if origins is not None else get_cors_origins()

    # In Starlette, allow_credentials=True with wildcard origin is supported via regex
    # to seamlessly support Kotlin Android WebView, emulator (10.0.2.2), and local browser apps.
    if "*" in allowed_origins:
        allow_origins: list[str] = []
        allow_origin_regex: str | None = r"^https?://.*$"
    else:
        allow_origins = allowed_origins
        allow_origin_regex = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=[
            "*",
            "X-Consent-Artifact-Id",
            "X-Farmer-Id",
            "Authorization",
            "Content-Type",
            "Accept",
            "X-Request-Id",
        ],
        expose_headers=[
            "X-Request-Id",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
            "X-Consent-Artifact-Id",
            "X-Farmer-Id",
        ],
    )


def classify_endpoint(path: str) -> tuple[Any, str]:
    """Classify the endpoint path into its rate limit tier: auth, prices, or general."""
    path_lower = path.lower()
    if any(k in path_lower for k in AUTH_PATH_KEYWORDS):
        return AUTH_LIMIT, "auth"
    if any(k in path_lower for k in PRICE_PATH_KEYWORDS):
        return PRICE_LIMIT, "prices"
    return GENERAL_LIMIT, "general"


def apply_security_headers(headers: Any) -> None:
    """Inject production security headers into the response headers mapping."""
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Frame-Options"] = "DENY"
    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=()"
    headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; sandbox"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that injects production security headers onto every HTTP response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        apply_security_headers(response.headers)
        return response


class RequestSizeLimiterMiddleware(BaseHTTPMiddleware):
    """Middleware restricting HTTP request body sizes to a maximum threshold (10MB)."""

    def __init__(self, app: Any, max_body_size: int = MAX_REQUEST_BODY_SIZE) -> None:
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_size:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Payload Too Large",
                            "detail": f"Request body exceeds maximum allowed size of {self.max_body_size // (1024 * 1024)}MB.",
                        },
                    )
            except ValueError:
                pass

        # Protect against chunked transfer encoding exceeding size limit
        received_bytes = 0
        original_receive = request.receive

        async def limited_receive():
            nonlocal received_bytes
            message = await original_receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                received_bytes += len(body)
                if received_bytes > self.max_body_size:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Request body exceeds maximum allowed size of {self.max_body_size // (1024 * 1024)}MB.",
                    )
            return message

        request._receive = limited_receive
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using SlowAPI with tiered endpoint limits.

    Tiers:
    - 20 req/min for auth / consent endpoints
    - 500 req/min for price and market intelligence endpoints
    - 100 req/min for general endpoints
    """

    def __init__(self, app: Any, slowapi_limiter: Limiter | None = None) -> None:
        super().__init__(app)
        self.limiter = slowapi_limiter or limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        # Exempt health probes and documentation from rate limiting
        if path in ("/health", "/ready", "/healthz", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        limit_item, category = classify_endpoint(path)
        client_ip = get_remote_address(request) or "127.0.0.1"
        key = f"{client_ip}:{category}"

        # Hit the slowapi storage backend
        is_allowed = self.limiter._limiter.hit(limit_item, key)
        stats = self.limiter._limiter.get_window_stats(limit_item, key)

        if not is_allowed:
            retry_after = max(1, int(stats.reset_time - time.time()))
            headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit_item.amount),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(stats.reset_time)),
            }
            apply_security_headers(headers)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Rate limit of {limit_item.amount} requests per minute exceeded for {category} endpoints.",
                },
                headers=headers,
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit_item.amount)
        response.headers["X-RateLimit-Remaining"] = str(max(0, stats.remaining))
        response.headers["X-RateLimit-Reset"] = str(int(stats.reset_time))
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """Composite security middleware combining request size limiting, tiered rate limiting,

    and security response headers in a unified high-performance layer.
    """

    def __init__(
        self,
        app: Any,
        max_body_size: int = MAX_REQUEST_BODY_SIZE,
        slowapi_limiter: Limiter | None = None,
    ) -> None:
        super().__init__(app)
        self.max_body_size = max_body_size
        self.limiter = slowapi_limiter or limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Request body size check
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_size:
                    resp = JSONResponse(
                        status_code=413,
                        content={
                            "error": "Payload Too Large",
                            "detail": f"Request body exceeds maximum allowed size of {self.max_body_size // (1024 * 1024)}MB.",
                        },
                    )
                    apply_security_headers(resp.headers)
                    return resp
            except ValueError:
                pass

        # 2. Rate limiting check via SlowAPI
        path = request.url.path
        is_exempt = path in ("/health", "/ready", "/healthz", "/docs", "/redoc", "/openapi.json")

        stats = None
        limit_item = None
        if not is_exempt:
            limit_item, category = classify_endpoint(path)
            client_ip = get_remote_address(request) or "127.0.0.1"
            key = f"{client_ip}:{category}"

            is_allowed = self.limiter._limiter.hit(limit_item, key)
            stats = self.limiter._limiter.get_window_stats(limit_item, key)

            if not is_allowed:
                retry_after = max(1, int(stats.reset_time - time.time()))
                headers = {
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit_item.amount),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(stats.reset_time)),
                }
                apply_security_headers(headers)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "detail": f"Rate limit of {limit_item.amount} requests per minute exceeded for {category} endpoints.",
                    },
                    headers=headers,
                )

        # 3. Process the downstream request
        response = await call_next(request)

        # 4. Inject Security Headers
        apply_security_headers(response.headers)

        # 5. Inject Rate Limit Headers
        if stats is not None and limit_item is not None:
            response.headers["X-RateLimit-Limit"] = str(limit_item.amount)
            response.headers["X-RateLimit-Remaining"] = str(max(0, stats.remaining))
            response.headers["X-RateLimit-Reset"] = str(int(stats.reset_time))

        return response
