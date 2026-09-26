"""Hardened UFSI / AgriStack JSON:API client with circuit breaker, PII redaction,
idempotency, and strict JSON:API parsing.

Implements the Unified Farmer Service Interface (UFSI) as mandated by the SRS
for AgriStack interoperability.

Features
--------
* **JSON:API wire format**: ``Content-Type: application/vnd.api+json``,
  sparse fieldsets, ``include`` for relationships, cursor-based pagination.
* **Farm ID validation**: Rejects anything that is not exactly
  ``2-char state + 11-digit random + 1 Verhoeff check digit``.
* **Circuit breaker**: Opens after N consecutive failures, half-open probe.
* **Retry with exponential backoff + jitter**.
* **Idempotency-Key on POSTs**.
* **Full request/response audit logging** with Aadhaar/farmer PII **redacted**.
* **JSON:API error mapping**: Upstream ``errors[].status/code/title/detail``
  mapped to our ``AppError`` taxonomy; raw upstream payloads never leak.
"""

from __future__ import annotations

import hashlib
import logging
import random
import re
import time
import uuid
from enum import Enum
from typing import Any

import httpx

from app.errors import AppError
from app.farmers.farm_id import FarmIdError, validate_farm_id

logger = logging.getLogger("app.integrations.ufsi")

# ── PII Redaction ──

_AADHAAR_PATTERN = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
_PHONE_PATTERN = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b")
_NAME_FIELDS = frozenset({
    "farmerName", "farmer_name", "displayName", "display_name",
    "name", "fatherName", "father_name", "spouseName", "spouse_name",
})


def _redact_value(key: str, value: Any) -> Any:
    """Redact PII from a single key-value pair."""
    if isinstance(value, str):
        # Always mask aadhaar-shaped strings
        value = _AADHAAR_PATTERN.sub("XXXX-XXXX-XXXX", value)
        value = _PHONE_PATTERN.sub("+91-XXXX-XXXXX", value)
    if isinstance(value, str) and key in _NAME_FIELDS:
        parts = value.strip().split()
        if parts:
            return parts[0][0] + "***" if parts[0] else "***"
    return value


def redact_payload(data: Any, *, _depth: int = 0) -> Any:
    """Recursively redact PII from a JSON-serializable structure.

    Safe to call on request bodies, response bodies, and log payloads.
    Limits recursion to prevent stack overflow on adversarial inputs.
    """
    if _depth > 20:
        return "<redacted:depth>"
    if isinstance(data, dict):
        return {k: _redact_value(k, redact_payload(v, _depth=_depth + 1)) for k, v in data.items()}
    if isinstance(data, list):
        return [redact_payload(item, _depth=_depth + 1) for item in data]
    return data


# ── JSON:API Parsing ──


class JsonApiParseError(Exception):
    """The upstream response did not conform to JSON:API."""


def parse_jsonapi_response(body: dict) -> dict:
    """Parse a JSON:API response strictly.

    Returns the flattened primary resource ``data.attributes`` dict merged with
    relationship data from ``included``.  Raises ``JsonApiParseError`` if
    the structure is malformed.
    """
    if "errors" in body:
        _raise_from_jsonapi_errors(body["errors"])

    data = body.get("data")
    if data is None:
        raise JsonApiParseError("JSON:API response missing 'data' key")

    if isinstance(data, list):
        return {"items": [_flatten_resource(r, body.get("included")) for r in data]}

    if not isinstance(data, dict):
        raise JsonApiParseError("JSON:API 'data' must be an object or array")

    return _flatten_resource(data, body.get("included"))


def _flatten_resource(resource: dict, included: list[dict] | None) -> dict:
    """Flatten a single JSON:API resource object."""
    result: dict[str, Any] = {}
    result["id"] = resource.get("id")
    result["type"] = resource.get("type")

    attributes = resource.get("attributes")
    if isinstance(attributes, dict):
        result.update(attributes)

    # Resolve relationships from included
    relationships = resource.get("relationships")
    if isinstance(relationships, dict) and included:
        included_map = {
            (r["type"], r["id"]): r for r in included if isinstance(r, dict)
        }
        for rel_name, rel_data in relationships.items():
            if not isinstance(rel_data, dict):
                continue
            link_data = rel_data.get("data")
            if isinstance(link_data, dict):
                key = (link_data.get("type"), link_data.get("id"))
                linked = included_map.get(key)
                if linked:
                    result[rel_name] = _flatten_resource(linked, None)
            elif isinstance(link_data, list):
                resolved = []
                for ld in link_data:
                    if isinstance(ld, dict):
                        key = (ld.get("type"), ld.get("id"))
                        linked = included_map.get(key)
                        if linked:
                            resolved.append(_flatten_resource(linked, None))
                result[rel_name] = resolved

    return result


def _raise_from_jsonapi_errors(errors: list) -> None:
    """Map JSON:API error objects into our error taxonomy.

    Never passes raw upstream error text to callers.
    """
    if not errors:
        raise JsonApiParseError("JSON:API errors array is empty")

    primary = errors[0] if isinstance(errors[0], dict) else {}
    status = int(primary.get("status", 500))
    code = primary.get("code", "UPSTREAM_ERROR")
    title = primary.get("title", "Upstream service error")
    detail = primary.get("detail", "")
    pointer = None
    source = primary.get("source")
    if isinstance(source, dict):
        pointer = source.get("pointer")

    # Map to our error taxonomy
    error_map = {
        400: (400, "VALIDATION_ERROR"),
        401: (401, "UNAUTHORIZED"),
        403: (403, "FORBIDDEN"),
        404: (404, "NOT_FOUND"),
        409: (409, "CONFLICT"),
        422: (422, "VALIDATION_ERROR"),
        429: (429, "RATE_LIMIT_EXCEEDED"),
    }
    mapped_status, mapped_code = error_map.get(status, (502, "EXTERNAL_SERVICE_ERROR"))

    # Sanitize: never pass raw upstream detail to our clients
    safe_detail = f"UFSI returned {mapped_code}"
    if pointer:
        safe_detail += f" (field: {pointer})"

    logger.warning(
        "UFSI JSON:API error: status=%s code=%s title=%s detail=%s pointer=%s",
        status, code, title,
        _AADHAAR_PATTERN.sub("XXXX-XXXX-XXXX", detail),  # Redact in logs too
        pointer,
    )

    raise AppError(mapped_status, safe_detail)


# ── Circuit Breaker ──


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Simple circuit breaker for external service calls."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout_s: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self.recovery_timeout_s:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning(
                "UFSI circuit breaker OPEN after %d consecutive failures",
                self._failures,
            )

    def check(self) -> None:
        """Raise AppError if circuit is open."""
        state = self.state
        if state == CircuitState.OPEN:
            raise AppError(
                503,
                "UFSI service temporarily unavailable (circuit breaker open)",
            )


# ── Hardened UFSI Client ──


class UfsiClient:
    """Production-grade UFSI JSON:API client.

    Replaces the naive ``app.farmers.ufsi.UfsiClient`` with full reliability,
    PII redaction, and JSON:API compliance.
    """

    JSON_API_MEDIA = "application/vnd.api+json"

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 15.0,
        max_retries: int = 3,
        backoff_base_s: float = 0.5,
        circuit_failure_threshold: int = 5,
        circuit_recovery_s: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self._circuit = CircuitBreaker(
            failure_threshold=circuit_failure_threshold,
            recovery_timeout_s=circuit_recovery_s,
        )
        self._transport = transport

    # ── Farm ID Validation ──

    @staticmethod
    def validate_farm_id(farm_id: str, *, state_lgd_code: str | None = None) -> str:
        """Validate that a farm ID is exactly 14 chars = 2-char state + 11-digit random + 1 Verhoeff.

        Rejects anything else before it reaches the domain layer.
        """
        if not farm_id or len(farm_id) != 14 or not farm_id.isdigit():
            raise AppError(
                422,
                f"Invalid farm ID format: must be exactly 14 digits, got '{farm_id}'",
            )
        try:
            return validate_farm_id(farm_id, state_lgd_code=state_lgd_code)
        except FarmIdError as exc:
            raise AppError(422, f"Invalid farm ID: {exc}") from exc

    # ── Core Request ──

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """Execute an HTTP request with retry, circuit breaker, and audit logging."""
        self._circuit.check()

        url = f"{self.base_url}{path}"
        headers: dict[str, str] = {
            "Accept": self.JSON_API_MEDIA,
            "Content-Type": self.JSON_API_MEDIA,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                # Audit log: request (PII-redacted)
                logger.info(
                    "UFSI request [attempt %d/%d]: %s %s params=%s body=%s",
                    attempt,
                    self.max_retries,
                    method,
                    url,
                    params,
                    redact_payload(json_body) if json_body else None,
                )

                from app.common.http_client import SafeAsyncClient

                async with SafeAsyncClient(
                    transport=self._transport,
                    allow_private=(self._transport is not None),
                    timeout=self.timeout_s,
                ) as client:
                    response = await client.request(
                        method,
                        url,
                        json=json_body,
                        params=params,
                        headers=headers,
                    )

                # Audit log: response (PII-redacted)
                try:
                    resp_body = response.json()
                except ValueError:
                    resp_body = {"_raw": response.text[:500]}

                logger.info(
                    "UFSI response [attempt %d]: status=%d body=%s",
                    attempt,
                    response.status_code,
                    redact_payload(resp_body),
                )

                if response.status_code >= 500:
                    self._circuit.record_failure()
                    raise httpx.HTTPStatusError(
                        f"Server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                self._circuit.record_success()

                if response.status_code >= 400:
                    # Try parsing as JSON:API error
                    try:
                        body = response.json()
                        if "errors" in body:
                            parse_jsonapi_response(body)  # Will raise AppError
                    except (ValueError, JsonApiParseError):
                        pass
                    raise AppError(response.status_code, f"UFSI returned {response.status_code}")

                return response.json()

            except AppError:
                raise
            except Exception as exc:
                last_exc = exc
                self._circuit.record_failure()
                if attempt < self.max_retries:
                    # Exponential backoff with jitter
                    delay = self.backoff_base_s * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    logger.warning(
                        "UFSI request failed (attempt %d/%d), retrying in %.2fs: %s",
                        attempt,
                        self.max_retries,
                        delay,
                        exc,
                    )
                    import asyncio
                    await asyncio.sleep(delay)

        raise AppError(502, "UFSI service unavailable after retries") from last_exc

    # ── Public API ──

    async def fetch_farmer_profile(
        self,
        *,
        farmer_id: str,
        state_lgd_code: str,
        consent_artifact_id: str,
        fields: list[str] | None = None,
        include: list[str] | None = None,
    ) -> dict:
        """Fetch a farmer profile by ID using JSON:API ``farmerProfileById``.

        Parameters
        ----------
        farmer_id:
            14-character farm registry ID (validated before request).
        state_lgd_code:
            LGD state code for the farmer's state.
        consent_artifact_id:
            Valid DEPA consent artifact ID (required by law).
        fields:
            Sparse fieldsets for the ``farmer`` resource type.
        include:
            Related resources to side-load (e.g. ``["landParcels", "cropSownRecords"]``).
        """
        # Validate farm ID before it reaches the wire
        self.validate_farm_id(farmer_id, state_lgd_code=state_lgd_code)

        params: dict[str, str] = {}
        if fields:
            params["fields[farmer]"] = ",".join(fields)
        if include:
            params["include"] = ",".join(include)

        body = {
            "data": {
                "type": "farmer-profiles",
                "attributes": {
                    "farmerId": farmer_id,
                    "stateLgdCode": state_lgd_code,
                    "consentArtifact": consent_artifact_id,
                },
            }
        }

        # Idempotency key for POST: hash of farmer_id + consent
        idem_key = hashlib.sha256(
            f"{farmer_id}:{consent_artifact_id}".encode()
        ).hexdigest()[:32]

        result = await self._request(
            "POST",
            "/farmerProfileById",
            json_body=body,
            params=params,
            idempotency_key=idem_key,
        )

        return parse_jsonapi_response(result)

    async def list_farmer_profiles(
        self,
        *,
        state_lgd_code: str,
        consent_artifact_id: str,
        page_number: int = 1,
        page_size: int = 20,
        include: list[str] | None = None,
    ) -> dict:
        """Paginated farmer profile listing using JSON:API pagination.

        Pagination uses ``page[number]`` / ``page[size]`` as specified by the SRS.
        """
        params: dict[str, str] = {
            "page[number]": str(page_number),
            "page[size]": str(page_size),
        }
        if include:
            params["include"] = ",".join(include)

        body = {
            "data": {
                "type": "farmer-profiles",
                "attributes": {
                    "stateLgdCode": state_lgd_code,
                    "consentArtifact": consent_artifact_id,
                },
            }
        }

        result = await self._request(
            "POST",
            "/farmerProfiles",
            json_body=body,
            params=params,
            idempotency_key=str(uuid.uuid4()),
        )

        return parse_jsonapi_response(result)

    @property
    def circuit_state(self) -> str:
        """Current circuit breaker state for health checks."""
        return self._circuit.state.value
