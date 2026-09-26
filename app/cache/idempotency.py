"""HTTP POST Idempotency Middleware and store.

Guarantees:
  - Idempotency-Key header support on all POST endpoints
  - Stores key -> (request fingerprint, response status, response body, response headers) for 24h
  - Replaying the same key with the SAME fingerprint returns the stored response
  - Replaying the same key with a DIFFERENT fingerprint returns HTTP 422 Unprocessable Entity
  - Request body SHA-256 hash is embedded into the fingerprint
"""

import base64
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.cache.client import CacheClient, format_cache_key, get_cache_client

logger = logging.getLogger("app.cache.idempotency")

IDEMPOTENCY_TTL_SECONDS: int = 86400  # 24 hours


def compute_request_fingerprint(
    method: str,
    path: str,
    body_bytes: bytes,
    tenant_or_client: str = "global",
) -> str:
    """Compute deterministic SHA-256 fingerprint of request method, path, tenant, and body."""
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    raw = f"{method.upper()}:{path}:{tenant_or_client}:{body_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class IdempotencyStore:
    """Storage layer for idempotency records backed by CacheClient."""

    def __init__(self, client: CacheClient | None = None) -> None:
        self.client = client or get_cache_client()

    def _build_key(self, idempotency_key: str, tenant: str = "global") -> str:
        return format_cache_key("idempotency", idempotency_key, tenant=tenant)

    async def get_record(self, idempotency_key: str, tenant: str = "global") -> dict[str, Any] | None:
        cache_key = self._build_key(idempotency_key, tenant)
        val = await self.client.get(cache_key)
        if not val:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    async def save_record(
        self,
        idempotency_key: str,
        fingerprint: str,
        status_code: int,
        body_bytes: bytes,
        headers: dict[str, str],
        tenant: str = "global",
        ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS,
    ) -> bool:
        cache_key = self._build_key(idempotency_key, tenant)
        record = {
            "fingerprint": fingerprint,
            "status_code": status_code,
            "body_b64": base64.b64encode(body_bytes).decode("ascii"),
            "headers": headers,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return await self.client.set(cache_key, json.dumps(record), ex=ttl_seconds)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware providing automatic Idempotency-Key support on POST requests."""

    def __init__(self, app: Any, store: IdempotencyStore | None = None) -> None:
        super().__init__(app)
        self.store = store or IdempotencyStore()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Only POST requests with Idempotency-Key header are handled
        if request.method.upper() != "POST":
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
        if not idempotency_key:
            return await call_next(request)

        idempotency_key = idempotency_key.strip()
        if not idempotency_key:
            return await call_next(request)

        # Extract tenant or client context
        tenant = (
            getattr(request.state, "tenant_id", None)
            or request.headers.get("X-Org-Id")
            or request.headers.get("X-Farmer-Id")
            or "global"
        )

        # Buffer request body so downstream endpoints can still read it
        body_bytes = await request.body()

        # Replace receive so subsequent handlers can read the buffered body
        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request._receive = receive

        fingerprint = compute_request_fingerprint(
            method=request.method,
            path=request.url.path,
            body_bytes=body_bytes,
            tenant_or_client=tenant,
        )

        # Check existing idempotency record
        existing = await self.store.get_record(idempotency_key, tenant=tenant)
        if existing:
            stored_fingerprint = existing.get("fingerprint")
            if stored_fingerprint == fingerprint:
                # Cache hit: exact fingerprint match -> replay stored response
                logger.info(
                    "Idempotency hit for key '%s'. Replaying stored %d response.",
                    idempotency_key,
                    existing.get("status_code", 200),
                )
                body_b64 = existing.get("body_b64", "")
                decoded_body = base64.b64decode(body_b64.encode("ascii"))
                headers = dict(existing.get("headers", {}))
                headers["X-Idempotent-Replayed"] = "true"
                headers["X-Cache-Lookup"] = "HIT"
                return Response(
                    content=decoded_body,
                    status_code=existing.get("status_code", 200),
                    headers=headers,
                )
            else:
                # Conflict: same key with different payload/fingerprint -> 422
                logger.warning(
                    "Idempotency conflict for key '%s'. Received fingerprint %s != stored %s.",
                    idempotency_key,
                    fingerprint,
                    stored_fingerprint,
                )
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": "Idempotency key conflict",
                        "detail": "Idempotency-Key was already used with a different request payload or endpoint.",
                    },
                    headers={"X-Idempotency-Conflict": "true"},
                )

        # Execute downstream request
        response = await call_next(request)

        # Cache response if successful or client validation error (< 500)
        if response.status_code < 500:
            # Read response body chunks
            response_body_bytes = b""
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    response_body_bytes += chunk.encode("utf-8")
                else:
                    response_body_bytes += chunk

            # Headers to preserve
            preserved_headers = {}
            for h_k in ("content-type", "content-encoding"):
                if h_k in response.headers:
                    preserved_headers[h_k] = response.headers[h_k]

            await self.store.save_record(
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                status_code=response.status_code,
                body_bytes=response_body_bytes,
                headers=preserved_headers,
                tenant=tenant,
                ttl_seconds=IDEMPOTENCY_TTL_SECONDS,
            )

            # Reconstruct response since body_iterator was consumed
            return Response(
                content=response_body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response
