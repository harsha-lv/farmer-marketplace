"""OpenAPI 3.1.0 Specification Builder & Enhancer.

Configures:
  - Comprehensive tag metadata with descriptions across all domain routers
  - Security schemes (Bearer JWT, API Key, Beckn Ed25519 signature)
  - Environment-aware server URLs from application settings
  - Consistent error response schemas & examples (400, 401, 403, 404, 422, 500)
"""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.config import Settings

OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "Authentication",
        "description": "User login, OAuth2 password flow, token refresh, RBAC role resolution, and client API key management.",
    },
    {
        "name": "prices",
        "description": "Real-time AGMARKNET mandi feeds, continuous rollups, modal price statistics, and ML-powered multi-horizon forecasting.",
    },
    {
        "name": "farmers",
        "description": "Farmer profile registry, land parcel boundaries, crop records, bank details, and localized KYC management.",
    },
    {
        "name": "consents",
        "description": "DPDP Act 2023 compliant consent artifacts, digital signatures, revocations, and audit logging.",
    },
    {
        "name": "agristack",
        "description": "Direct integration with India AgriStack registries (Farmer ID, Land Registry, Georeferenced plots).",
    },
    {
        "name": "lots",
        "description": "Commodity lot creation, inventory tracking, quality status lifecycle (UNASSAYED -> ASSAYED -> LISTED -> LOCKED -> SOLD).",
    },
    {
        "name": "trades",
        "description": "Bilateral trade contract execution, counter-negotiations, escrow settlement triggers, and dispute holds.",
    },
    {
        "name": "sync",
        "description": "WatermelonDB-compatible bidirectional offline-first sync protocol for low-connectivity Android field devices.",
    },
    {
        "name": "events",
        "description": "Transactional outbox events, event replay, and streaming relay status.",
    },
    {
        "name": "finance",
        "description": "Electronic Negotiable Warehouse Receipt (e-NWR) pledge loans, LTV assessment, lien registration, and repayments.",
    },
    {
        "name": "telemetry",
        "description": "Per-FPO NATS JetStream telemetry, IoT sensor queues, edge heartbeats, and backpressure metrics.",
    },
    {
        "name": "logistics",
        "description": "PostGIS haulage routing, cold-chain tariff computation, vehicle profiles, and ONDC LSP network quote aggregation.",
    },
    {
        "name": "logistics_webhooks",
        "description": "Asynchronous ONDC LSP webhook ingestion for tracking updates, proof-of-delivery, and carrier status.",
    },
    {
        "name": "grievances",
        "description": "ONDC Issue & Grievance Management (IGM) tickets, respondent actions, escalation workflows, and resolutions.",
    },
    {
        "name": "ratings",
        "description": "Two-sided trust ratings and reviews for farmers, FPOs, logistics providers, and institutional buyers.",
    },
    {
        "name": "assay-ai",
        "description": "Computer vision quality inspection, grain defect detection, moisture grading, and tamper-evident HMAC signing.",
    },
    {
        "name": "admin-lgd",
        "description": "Local Government Directory (LGD) reconciliation, mandi code resolution, state/district/sub-district mapping.",
    },
    {
        "name": "beckn",
        "description": "ONDC Beckn protocol BPP (Seller) endpoints: discovery, order lifecycle, tracking, and cancellation callbacks.",
    },
    {
        "name": "beckn_bap",
        "description": "ONDC Beckn protocol BAP (Buyer) client querying external logistics service providers (LSPs) and partner networks.",
    },
    {
        "name": "health",
        "description": "Kubernetes liveness, readiness, and startup health probes with downstream dependency health checks.",
    },
]


def build_servers(settings: Settings) -> list[dict[str, str]]:
    """Build list of environment-aware API servers."""
    servers = [
        {
            "url": "http://localhost:8000",
            "description": "Local Development Server",
        },
    ]

    if settings.environment.lower() == "staging":
        servers.insert(0, {
            "url": "https://staging-api.agrimarket.local",
            "description": "Staging Environment (ONDC Pre-Production Staging)",
        })
    elif settings.environment.lower() in ("production", "prod"):
        servers.insert(0, {
            "url": "https://api.agrimarket.local",
            "description": "Production API Gateway (ONDC Live Network)",
        })

    if settings.ondc_bpp_uri:
        servers.append({
            "url": settings.ondc_bpp_uri,
            "description": f"ONDC Beckn BPP Endpoint ({settings.ondc_bpp_id})",
        })

    return servers


def build_security_schemes() -> dict[str, Any]:
    """Define OpenAPI 3.1.0 security components."""
    return {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Standard JSON Web Token (JWT) issued by `/api/v1/auth/token`. "
                "Include in HTTP headers as `Authorization: Bearer <token>`."
            ),
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": (
                "Partner & Gateway API Key for service-to-service access. "
                "Include in HTTP headers as `X-API-Key: <key>`."
            ),
        },
        "BecknSignatureAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": (
                "ONDC / Beckn ed25519 asymmetric cryptographic signature header. "
                "Format: `Signature keyId=\"...\",algorithm=\"ed25519\",created=\"...\",expires=\"...\",headers=\"(request-target) ...\",signature=\"...\"`"
            ),
        },
    }


def build_error_components() -> dict[str, Any]:
    """Define standard error envelope schemas and responses."""
    return {
        "ErrorEnvelope": {
            "type": "object",
            "title": "ErrorEnvelope",
            "description": "Standardized JSON error envelope emitted on 4xx/5xx failures.",
            "properties": {
                "error": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Machine-readable uppercase error identifier.",
                            "example": "RESOURCE_NOT_FOUND",
                        },
                        "message": {
                            "type": "string",
                            "description": "Human-readable explanation of the error.",
                            "example": "The requested commodity lot does not exist.",
                        },
                        "details": {
                            "type": "object",
                            "nullable": True,
                            "description": "Optional domain-specific diagnostic payload.",
                            "example": {"lot_id": "lot-7b3dcb6d-3b7d-4bad"},
                        },
                    },
                    "required": ["code", "message"],
                },
                "request_id": {
                    "type": "string",
                    "description": "Correlated trace / request identifier from RequestIDMiddleware.",
                    "example": "req-9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                },
                "timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "description": "UTC timestamp of the error response.",
                    "example": "2026-09-26T00:30:00Z",
                },
            },
            "required": ["error"],
        },
        "ValidationErrorEnvelope": {
            "type": "object",
            "title": "ValidationErrorEnvelope",
            "description": "Pydantic request validation error envelope (HTTP 422).",
            "properties": {
                "detail": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "loc": {
                                "type": "array",
                                "items": {"type": "string"},
                                "example": ["body", "quantity_quintals"],
                            },
                            "msg": {
                                "type": "string",
                                "example": "Input should be greater than 0",
                            },
                            "type": {
                                "type": "string",
                                "example": "greater_than",
                            },
                        },
                        "required": ["loc", "msg", "type"],
                    },
                },
                "request_id": {
                    "type": "string",
                    "example": "req-9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                },
            },
            "required": ["detail"],
        },
    }


def generate_custom_openapi(app: FastAPI) -> dict[str, Any]:
    """Compile polished OpenAPI 3.1.0 specification."""
    if app.openapi_schema:
        return app.openapi_schema

    settings: Settings = getattr(app.state, "settings", None) or Settings()

    openapi_schema = get_openapi(
        title=settings.app_name,
        version=settings.app_version,
        openapi_version="3.1.0",
        description=(
            "### Agri-Market Intelligence Platform API\n\n"
            "High-throughput, offline-first digital marketplace backend powering:\n"
            "- **Farmer & FPO Registry**: AgriStack KYC, land parcels, DPDP Act 2023 consents\n"
            "- **Quality Assay AI**: Grain CV classification with tamper-evident HMAC signing\n"
            "- **Mandi Price Intelligence**: Continuous AGMARKNET aggregations & TFT ML forecasting\n"
            "- **Trade Execution**: Bilateral contracts, pledge finance, and warehouse liens\n"
            "- **ONDC Integration**: BPP seller gateway, BAP LSP logistics quote aggregator & IGM grievances\n"
            "- **Edge Synchronization**: WatermelonDB-compatible delta sync protocol for Kotlin Android clients\n\n"
            "**Single Source of Truth Documentation**: See `docs/API_CONTRACT.md` and `SYNC_CONTRACT.md`."
        ),
        routes=app.routes,
        tags=OPENAPI_TAGS,
        servers=build_servers(settings),
    )

    # Ensure components structure
    components = openapi_schema.setdefault("components", {})
    components.setdefault("schemas", {}).update(build_error_components())
    components["securitySchemes"] = build_security_schemes()

    # Standard default security applies to the API
    openapi_schema.setdefault("security", [{"BearerAuth": []}])

    # Add consistent error responses to all paths if not explicitly configured
    default_error_responses = {
        "400": {
            "description": "Bad Request - Invalid payload or business constraint violation.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
        },
        "401": {
            "description": "Unauthorized - Missing or expired Bearer JWT / API Key.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
        },
        "403": {
            "description": "Forbidden - Insufficient RBAC role or tenant permission.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
        },
        "404": {
            "description": "Not Found - Entity or resource does not exist.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
        },
        "422": {
            "description": "Unprocessable Entity - Schema validation failed.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ValidationErrorEnvelope"}}},
        },
        "500": {
            "description": "Internal Server Error - Unhandled exception with correlated request_id.",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
        },
    }

    paths = openapi_schema.get("paths", {})
    for path_item in paths.values():
        for method, operation in path_item.items():
            if isinstance(operation, dict):
                responses = operation.setdefault("responses", {})
                for status_code, err_spec in default_error_responses.items():
                    if status_code not in responses:
                        responses[status_code] = err_spec

    app.openapi_schema = openapi_schema
    return app.openapi_schema
