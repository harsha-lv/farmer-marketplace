"""Backwards-compatible Beckn v1.2.0 to v2.0.0 protocol translation shim.

Guarantees:
  - Detects incoming Beckn v1.2.0 requests
  - Translates v1 payload into canonical v2.0.0 internal representation
  - Translates response back to v1.2.0 format for v1 callers
  - Emits standard Deprecation, Sunset, and Link response headers
"""

from typing import Any

from fastapi import Response

from app.ondc.schemas import (
    DEFAULT_JSONLD_CONTEXT,
    DOMAIN_AGRICULTURE,
    PROTOCOL_VERSION_V1,
    PROTOCOL_VERSION_V2,
)

DEPRECATION_DATE = "Wed, 31 Dec 2026 23:59:59 GMT"
V2_SUCCESSOR_LINK = '<https://ondc.org/v2>; rel="successor-version"'


def is_v1_request(body: dict[str, Any] | None) -> bool:
    """Check whether incoming request carries Beckn Protocol v1.2.0."""
    if not isinstance(body, dict):
        return False
    context = body.get("context")
    if not isinstance(context, dict):
        return False
    version = str(context.get("version", "")).strip()
    core_version = str(context.get("core_version", "")).strip()
    return version == PROTOCOL_VERSION_V1 or core_version == PROTOCOL_VERSION_V1 or version.startswith("1.")


def translate_v1_to_v2(body: dict[str, Any]) -> dict[str, Any]:
    """Translate v1.2.0 request envelope to v2.0.0 internal domain representation."""
    upgraded = dict(body)
    context = dict(upgraded.get("context", {}))

    # Add JSON-LD block
    if "@context" not in context:
        context["@context"] = DEFAULT_JSONLD_CONTEXT

    # Upgrade version and domain
    context["version"] = PROTOCOL_VERSION_V2
    context["core_version"] = PROTOCOL_VERSION_V2
    if not context.get("domain") or "AGR" not in context.get("domain", ""):
        context["domain"] = DOMAIN_AGRICULTURE

    upgraded["context"] = context
    return upgraded


def translate_v2_to_v1(response_data: dict[str, Any]) -> dict[str, Any]:
    """Translate v2.0.0 response envelope back to v1.2.0 format for legacy callers."""
    downgraded = dict(response_data)
    if "context" in downgraded and isinstance(downgraded["context"], dict):
        ctx = dict(downgraded["context"])
        ctx["version"] = PROTOCOL_VERSION_V1
        ctx["core_version"] = PROTOCOL_VERSION_V1
        downgraded["context"] = ctx
    return downgraded


def apply_deprecation_headers(response: Response) -> Response:
    """Tag response with standard HTTP deprecation headers for v1.2.0 clients."""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = DEPRECATION_DATE
    response.headers["Link"] = V2_SUCCESSOR_LINK
    return response
