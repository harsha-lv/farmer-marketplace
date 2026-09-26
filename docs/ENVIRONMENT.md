# Environment Reference — Agri-Market Intelligence Platform

This document is the **authoritative reference** for every environment variable consumed by
the platform.  It is generated from `app/config.py` and augmented with connection semantics,
priority rules, and operational guidance.

---

## Variable Lookup Priority

```
Real OS env vars  >  .env file  >  pydantic-settings defaults
```

* All settings live in `app/config.py` as a `pydantic-settings` `Settings` class.
* Primary form: `APP_<FIELD_NAME_UPPER>` (e.g. `APP_DATABASE_URL`).
* Many fields accept a **bare alias** (legacy or spec-defined) via `AliasChoices`
  — these are documented in the table below under the *Accepted aliases* column.
* Nested delimiter `__` is supported for future nesting (e.g. `APP_KAFKA__BOOTSTRAP_SERVERS`
  is equivalent to `APP_KAFKA_BOOTSTRAP_SERVERS`).
* `OTEL_*` variables follow the OpenTelemetry specification and carry **no `APP_` prefix**.

---

## Quick-start (local development)

```bash
# 1. Copy the template
cp .env.example .env

# 2. Generate dev secrets (safe, random, not for production)
python scripts/gen_dev_secrets.py --write

# 3. Validate configuration and connectivity
python scripts/check_env.py
```

For production, also run:
```bash
python scripts/check_env.py --production
```

---

## Variable Reference

### Application

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_ENVIRONMENT` | `local` | — | Runtime tier: `local` \| `staging` \| `production` |
| `APP_LOG_LEVEL` | `INFO` | `LOG_LEVEL` | Log verbosity: `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `APP_APP_NAME` | `Agri-Market Intelligence Platform` | — | Service display name |
| `APP_APP_VERSION` | `0.1.0` | — | Semantic version string |

### Database

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_DATABASE_URL` | `postgresql+asyncpg://app:app@localhost:5432/app` | — | asyncpg DSN. Must use `+asyncpg` driver. |
| `APP_DB_STATEMENT_TIMEOUT_MS` | `15000` | `DB_STATEMENT_TIMEOUT_MS` | Per-query hard timeout in ms. |
| `APP_CHECK_ALEMBIC_HEAD` | `false` | `CHECK_ALEMBIC_HEAD` | Verify DB schema at head on startup. |

### Security / JWT

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_JWT_SECRET_KEY` | *(dev placeholder)* | — | HMAC-SHA256 secret. **Must be ≥ 32 chars and unique in production.** Generate with `python scripts/gen_dev_secrets.py`. |
| `APP_JWT_ALGORITHM` | `HS256` | — | JWT signing algorithm. |
| `APP_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | — | Short-lived access token TTL. |
| `APP_JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `30` | — | Refresh token TTL. |

### Redis / Cache

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_REDIS_URL` | *(empty — cache disabled)* | `REDIS_URL` | Redis DSN, e.g. `redis://localhost:6379/0`. |
| `APP_REDIS_POOL_SIZE` | `50` | `REDIS_POOL_SIZE` | Connection pool size. |
| `APP_REDIS_TIMEOUT_MS` | `1500` | `REDIS_TIMEOUT_MS` | Socket timeout in ms. |
| `APP_CACHE_ENABLED` | `true` | `CACHE_ENABLED` | Toggle cache entirely. |

### CORS

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_CORS_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | `CORS_ORIGINS` | Comma-separated list of allowed origins. Wildcard `*` is accepted only without credentials. |

### Kafka

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_KAFKA_BOOTSTRAP_SERVERS` | *(empty — Kafka disabled)* | — | Comma-separated broker list, e.g. `broker1:9092,broker2:9092`. |
| `APP_KAFKA_CLIENT_ID` | `agri-platform` | — | Kafka producer/consumer client ID. |
| `APP_KAFKA_ACKS` | `all` | — | Producer acks mode (`all` for idempotent delivery). |
| `APP_KAFKA_ENABLE_IDEMPOTENCE` | `true` | — | Producer idempotence. |
| `APP_KAFKA_LINGER_MS` | `10` | — | Producer linger for micro-batching. |
| `APP_KAFKA_MAX_BATCH_SIZE` | `16384` | — | Producer batch size in bytes. |
| `APP_KAFKA_MAX_RETRY_ATTEMPTS` | `5` | — | Max delivery retries. |
| `APP_KAFKA_RETRY_BACKOFF_MS` | `100` | — | Initial backoff between retries. |
| `APP_KAFKA_DLQ_TOPIC` | `agri.dlq` | — | Dead-letter queue topic. |
| `APP_KAFKA_DEFAULT_RETENTION_MS` | `604800000` (7 days) | — | Default topic retention. |
| `APP_KAFKA_COMPLIANCE_RETENTION_MS` | `31536000000` (1 year) | — | Compliance-grade retention for audit logs. |

### NATS JetStream

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_NATS_URL` | *(empty — NATS disabled)* | — | NATS server URL, e.g. `nats://localhost:4222`. |
| `APP_NATS_JETSTREAM_MAX_MESSAGES` | `100000` | — | Per-stream message limit. |
| `APP_NATS_JETSTREAM_MAX_BYTES` | `104857600` (100 MiB) | — | Per-stream byte limit. |
| `APP_NATS_JETSTREAM_MAX_AGE_SECONDS` | `604800` (7 days) | — | Per-stream age retention. |
| `APP_NATS_JETSTREAM_DEDUP_WINDOW_SECONDS` | `120` | — | Dedup window for idempotent message delivery. |

### Event Outbox

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_EVENT_OUTBOX_BATCH_SIZE` | `100` | — | Number of outbox rows fetched per relay cycle. |

### External Data APIs

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_DATA_GOV_API_KEY` | *(empty)* | — | data.gov.in API key for AGMARKNET price ingestion. **Required in production.** |
| `APP_DATA_GOV_RESOURCE_URL` | *(AGMARKNET endpoint)* | — | Resource URL override. |
| `APP_OPENWEATHER_API_KEY` | *(empty)* | `OPENWEATHER_API_KEY` | OpenWeatherMap API key. Falls back to `IMD_API_KEY`. Omit for deterministic agro-climatic baseline mode. |
| `APP_IMD_API_KEY` | *(empty)* | `IMD_API_KEY` | IMD API key (secondary weather source). |

### AgriStack / UFSI

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_UFSI_BASE_URL` | *(empty)* | — | Unified Farmer Service Interface base URL. |
| `APP_AGRISTACK_API_KEY` | *(empty)* | — | AgriStack API key. |
| `APP_AGRISTACK_BASE_URL` | *(empty)* | — | AgriStack API base URL. |

### Consent / Assay Signing

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_CONSENT_SIGNING_SECRET` | *(empty)* | — | HMAC secret for consent artifact signing. **Must be set in production.** |
| `APP_ASSAY_HMAC_SECRET` | *(dev placeholder)* | `ASSAY_HMAC_SECRET` | HMAC secret for assay tamper-evidence. **Must be set in production.** |

### ONDC / Beckn BPP

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_ONDC_BPP_ID` | `market.local` | — | BPP subscriber ID registered on ONDC network. |
| `APP_ONDC_BPP_URI` | `http://127.0.0.1:8000/beckn` | — | BPP callback URI. |
| `APP_ONDC_BPP_NAME` | `Market desk` | — | Human-readable BPP name. |
| `APP_ONDC_COMMISSION_PERCENT` | `0` | — | Platform commission percentage. |
| `APP_ONDC_SUPPORT_PHONE` | `+911800123456` | — | Grievance support phone. |
| `APP_ONDC_SUPPORT_EMAIL` | `grievance@market.local` | — | Grievance support email. |
| `APP_ONDC_TRACKING_BASE_URL` | `https://track.market.local/shipments` | — | Shipment tracking URL prefix. |
| `APP_ONDC_AUTH_ENABLED` | `false` | — | Enable Ed25519 Beckn signature verification on inbound requests. |
| `APP_ONDC_SIGNING_PRIVATE_KEY_HEX` | *(empty — dev seed used)* | `ONDC_SIGNING_PRIVATE_KEY_HEX` | Hex-encoded 32-byte Ed25519 private key seed. **Required when `ONDC_AUTH_ENABLED=true` in production.** Generate with `python scripts/gen_dev_secrets.py`. |
| `APP_ONDC_UNIQUE_KEY_ID` | `key-1` | — | `ukId` field in Beckn `Signature` header. |

### ONDC / Beckn BAP

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_ONDC_BAP_ID` | `buyer.market.local` | — | BAP subscriber ID. |
| `APP_ONDC_BAP_URI` | `http://127.0.0.1:8000/beckn/bap` | — | BAP callback URI. |
| `APP_ONDC_REGISTRY_URL` | `http://127.0.0.1:8000/beckn/registry` | — | ONDC registry lookup URL. Production: `https://prod.registry.ondc.org/...` |

### eNAM

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_ENAM_BASE_URL` | *(empty — eNAM disabled)* | — | eNAM government portal API base URL. |

### e-RUPI / Settlement

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_ERUPI_ISSUER_ID` | `ONDC-RSP-PARTNER-BANK` | — | e-RUPI issuing bank partner ID. |
| `APP_ERUPI_VALIDITY_DAYS` | `30` | — | e-RUPI voucher validity in days. |
| `APP_SETTLEMENT_TDS_RATE_BPS` | `100` (1%) | — | TDS deduction rate in basis points. |

### Pledge Finance

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_PLEDGE_FINANCE_DEFAULT_LTV_BPS` | `7500` (75%) | — | Default Loan-to-Value ratio in bps. |
| `APP_PLEDGE_FINANCE_DEFAULT_INTEREST_BPS` | `700` (7%) | — | Default annual interest rate in bps. |
| `APP_PLEDGE_FINANCE_DEFAULT_LENDER` | `NABARD Agri-Credit Partner Bank` | — | Default lender name. |

### HTTP Client (outbound)

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_HTTP_CONNECT_TIMEOUT_SECONDS` | `5.0` | `HTTP_CONNECT_TIMEOUT_SECONDS` | TCP connect timeout. |
| `APP_HTTP_READ_TIMEOUT_SECONDS` | `15.0` | `HTTP_READ_TIMEOUT_SECONDS` | Response read timeout. |
| `APP_HTTP_WRITE_TIMEOUT_SECONDS` | `10.0` | `HTTP_WRITE_TIMEOUT_SECONDS` | Request write timeout. |
| `APP_HTTP_POOL_TIMEOUT_SECONDS` | `5.0` | `HTTP_POOL_TIMEOUT_SECONDS` | Pool acquire timeout. |
| `APP_HTTP_MAX_REDIRECTS` | `5` | `HTTP_MAX_REDIRECTS` | Max followed redirects. |
| `APP_HTTP_SSRF_ALLOW_PRIVATE` | `false` | `HTTP_SSRF_ALLOW_PRIVATE` | Allow outbound calls to RFC-1918 private IP ranges (dev only). |
| `APP_MAX_REQUEST_BODY_SIZE_BYTES` | `52428800` (50 MiB) | — | Inbound request body size limit. |

### Server

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_SERVER_REQUEST_TIMEOUT_SECONDS` | `30.0` | `SERVER_REQUEST_TIMEOUT_SECONDS` | Hard per-request timeout applied by `TimeoutMiddleware`. |

### Rate Limiting

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_RATE_LIMIT_PER_MINUTE_DEFAULT` | `100` | — | Default endpoint rate limit. |
| `APP_RATE_LIMIT_PER_MINUTE_AUTH` | `20` | — | Auth endpoint rate limit. |
| `APP_RATE_LIMIT_PER_MINUTE_PRICES` | `500` | — | Prices/forecast endpoint rate limit. |

### Inference / ML

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_INFERENCE_CONCURRENCY` | `4` | `INFERENCE_CONCURRENCY` | Number of concurrent ONNX inference requests. |
| `APP_INFERENCE_TIMEOUT_MS` | `5000` | `INFERENCE_TIMEOUT_MS` | Per-inference hard timeout in ms. |
| `APP_MODELS_DIR` | `models` | `MODELS_DIR` | Path to ONNX model artefacts directory. |

### Observability — OpenTelemetry

> These variables follow the **OpenTelemetry specification** and carry no `APP_` prefix.
> They are also accepted with the `APP_` prefix for consistency.

| Variable | Default | Description |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *(empty — tracing disabled)* | OTLP gRPC endpoint, e.g. `http://otel-collector:4317`. When empty, all instrumentation is a strict NO-OP. |
| `OTEL_SERVICE_NAME` | `agri-platform-backend` | Service name reported to the trace backend. |
| `OTEL_EXPORTER_OTLP_INSECURE` | `true` | Set to `false` in production when using TLS on the OTLP endpoint. |

### Observability — Prometheus

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `METRICS_BEARER_TOKEN` | *(empty — endpoint unprotected)* | `APP_METRICS_TOKEN` | Bearer token for `GET /metrics`. **Must be set in production.** |

### Worker Processes

| Variable | Default | Accepted aliases | Description |
|---|---|---|---|
| `APP_RUN_WORKERS_INLINE` | `false` | `RUN_WORKERS_INLINE` | Run ingestion/relay workers inside the web process (dev convenience only). Never set in production — use dedicated worker containers instead. |

---

## Production Checklist

The `validate_production()` method in `Settings` will reject a startup if any of the following
are missing or still contain dev placeholders when `APP_ENVIRONMENT=production`:

| Check | Variable |
|---|---|
| JWT secret set and ≥ 32 chars | `APP_JWT_SECRET_KEY` |
| Redis configured | `APP_REDIS_URL` |
| Kafka configured | `APP_KAFKA_BOOTSTRAP_SERVERS` |
| NATS configured | `APP_NATS_URL` |
| Metrics endpoint protected | `METRICS_BEARER_TOKEN` |
| Consent signing secret set | `APP_CONSENT_SIGNING_SECRET` |
| Assay HMAC secret not default | `APP_ASSAY_HMAC_SECRET` |
| Ed25519 key set (if auth enabled) | `APP_ONDC_SIGNING_PRIVATE_KEY_HEX` |
| Price ingestion key present | `APP_DATA_GOV_API_KEY` |

Run the full production check before any deployment:

```bash
APP_ENVIRONMENT=production python scripts/check_env.py --production
```

---

## Secret Generation

Use the provided script to generate all required secrets:

```bash
# Print to stdout (review first)
python scripts/gen_dev_secrets.py

# Write directly into .env (safe for local dev)
python scripts/gen_dev_secrets.py --write
```

The script generates:

| Secret | Length | Purpose |
|---|---|---|
| `APP_JWT_SECRET_KEY` | 64 hex chars | JWT HMAC-SHA256 signing |
| `APP_CONSENT_SIGNING_SECRET` | 64 hex chars | Consent artifact HMAC |
| `APP_ASSAY_HMAC_SECRET` | 64 hex chars | Assay report tamper-evidence |
| `APP_ONDC_SIGNING_PRIVATE_KEY_HEX` | 64 hex chars | Ed25519 Beckn signing seed |
| `METRICS_BEARER_TOKEN` | 48 hex chars | Prometheus /metrics auth |

> **Rule**: No secret may appear in `.env.example`. The example file contains only
> `CHANGE_ME` placeholders.

---

## Reconciliation: Variables Not in `Settings`

These variables are consumed directly by the Python runtime or by third-party SDK
conventions, and intentionally live outside `app/config.py`:

| Variable | Consumer | Notes |
|---|---|---|
| `PYTHONPATH` | Python runtime | Set by Docker/CI, not the app. |
| `PYTHONDONTWRITEBYTECODE` | Python runtime | Docker optimisation. |
| `PYTHONUNBUFFERED` | Python runtime | Docker log streaming. |
| `UVICORN_HOST` / `UVICORN_PORT` | Dockerfile `CMD` | Overridable via docker-compose. |
| `PROMETHEUS_MULTIPROC_DIR` | `prometheus-client` | Required for multi-process metrics. Set to a writable tmpdir. |
