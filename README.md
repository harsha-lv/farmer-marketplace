# Agri-Market Intelligence Platform

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1.0-green.svg)](https://swagger.io/specification/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)]()

Production-grade, offline-first digital marketplace backend powering agricultural trade, AI grain quality inspection, real-time mandi intelligence, DPDP Act 2023 consent architecture, and ONDC Beckn protocol integration for Farmer Producer Organizations (FPOs) across India.

---

## 1. System Architecture

```mermaid
flowchart TD
    subgraph Clients["Edge & Network Clients"]
        Android["Kotlin Android App (WatermelonDB / SQLite)"]
        WebPortal["FPO & Buyer Web Portal"]
        ONDCGateway["ONDC Network Gateway (BAP / BPP)"]
    end

    subgraph Gateway["API & Telemetry Gateway"]
        FastAPI["FastAPI 0.115+ (ASGI Engine)"]
        AuthMiddleware["JWT / API-Key / Beckn Ed25519 Auth"]
        SecMiddleware["Rate Limiter & Size Guard (50MB)"]
    end

    subgraph CoreServices["Domain Services & Engines"]
        SyncService["Offline Sync Engine (LWW)"]
        AssayEngine["AI Quality Assay Engine (ONNX)"]
        ForecastingEngine["TFT / LSTM Price Forecaster (Pinball Loss)"]
        TradeService["Bilateral Trade & Escrow Contracts"]
        LogisticsEngine["PostGIS Routing & ONDC LSP Aggregator"]
        GrievanceService["ONDC IGM Issue Ticketing"]
    end

    subgraph Messaging["Event Streaming & Telemetry"]
        NATS["NATS JetStream (Per-FPO Streams & RPC)"]
        Kafka["Apache Kafka (Immutable Outbox & ML Replay)"]
    end

    subgraph Storage["Databases & Caching"]
        PG[(PostgreSQL 16 + PostGIS + TimescaleDB)]
        Redis[(Redis 7 Cluster: Cache & Idempotency)]
        Disk[(Model Registry: ONNX & TFT Weights)]
    end

    Android <-->|GET/POST /api/v1/sync| SyncService
    WebPortal -->|REST API| FastAPI
    ONDCGateway <-->|Beckn Protocol /beckn| FastAPI

    FastAPI --> AuthMiddleware --> SecMiddleware
    SecMiddleware --> CoreServices

    AssayEngine --> Disk
    ForecastingEngine --> Disk

    CoreServices <--> PG
    CoreServices <--> Redis
    CoreServices --> NATS
    CoreServices --> Kafka
```

---

## 2. Key Features

- **Offline-First Synchronization**: WatermelonDB-compatible delta sync engine (`/api/v1/sync`) supporting low-connectivity Android field devices with deterministic Last-Write-Wins (LWW) and soft-delete tombstones.
- **AI Grain Quality Assay**: Computer vision inspection powered by ONNX Runtime with multi-image defect segmentation, moisture estimation, and tamper-evident HMAC signing.
- **Mandi Intelligence & ML Forecasting**: Continuous TimescaleDB rollups of AGMARKNET feeds; Temporal Fusion Transformer (TFT) with quantile pinball loss ($p10/p50/p90$) and multi-horizon decision breakdown (`STORE`, `SELL`, `HEDGE`).
- **ONDC Beckn Protocol**: Native dual-role support acting as **BPP (Seller)** for commodity discovery/orders and **BAP (Buyer)** for 3rd-party logistics (LSP) quote aggregation and tracking webhooks.
- **DPDP Act 2023 Consents**: Asymmetric cryptographic signing, time-bounded data purpose artifacts, and automated revocation cascades.
- **Hybrid Streaming**: NATS JetStream for dynamic per-tenant FPO telemetry and async RPC; Apache Kafka for immutable audit logging and ML training replay.

---

## 3. Local Development Quickstart

### Prerequisites
- Python 3.12+
- Docker & Docker Compose
- Node.js (optional, for Swagger UI validation)

### 1. Clone & Set Up Virtual Environment
```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

pip install -e ".[dev]"
```

### 2. Start Infrastructure Services
```bash
docker compose up -d postgres redis nats kafka
```

### 3. Apply Database Migrations
```bash
alembic upgrade head
```

### 4. Start the Application Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server is available at:
- **API Base**: `http://localhost:8000`
- **Interactive OpenAPI Documentation**: `http://localhost:8000/docs`
- **OpenAPI 3.1.0 Raw Spec**: `http://localhost:8000/openapi.json`
- **Prometheus Metrics**: `http://localhost:8000/metrics`
- **Liveness & Readiness**: `http://localhost:8000/health`, `http://localhost:8000/ready`

### 5. Web Frontend & Development Server (VS Code Live Server)
In local development, the frontend is served as static HTML/ES modules via VS Code Live Server:
- **Dev Origin**: `http://127.0.0.1:5500` (or `http://localhost:5500`)
- **API Routing**: Handled by `web/config.js`, which automatically resolves to absolute `http://127.0.0.1:8000/api/v1` in local development mode, avoiding requests against the static port 5500 server.
- **CORS Allowlist**: The backend explicitly allows dev origins (`http://127.0.0.1:5500`, `http://localhost:5500`) with credential support and exposed security headers.
- **Production Mode**: In production environments behind a reverse proxy, `web/config.js` falls back to same-origin `/api/v1`.
- **Developer Overrides**: Set `window.__AGRI_CONFIG__.apiBaseUrl` or `localStorage.setItem('agri.apiBase', 'http://...')` to override the API target.

---

## 4. Environment Variables Reference

All settings can be configured via environment variables or a `.env` file with the `APP_` prefix:

| Environment Variable | Default Value | Description & Production Guidance |
|:---|:---|:---|
| `APP_DATABASE_URL` | `postgresql+asyncpg://app:app@localhost:5432/app` | PostgreSQL async connection URI with PostGIS and TimescaleDB. |
| `APP_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL for caching, rate limiting, and idempotency. |
| `APP_KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Comma-separated Kafka broker addresses for event outbox streaming. |
| `APP_NATS_URL` | `nats://localhost:4222` | NATS JetStream cluster connection URL. |
| `APP_JWT_SECRET_KEY` | `dev-secret-key-change-in-production...` | Secret key for HS256 JWT access tokens (min 32 characters in prod). |
| `APP_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token TTL in minutes. |
| `APP_JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token TTL in days. |
| `APP_ASSAY_HMAC_SECRET` | `assay-tamper-evident-hmac-secret...` | Secret key for SHA-256 HMAC digital signatures on assay reports. |
| `APP_ONDC_BPP_ID` | `market.local` | ONDC registered Subscriber ID for this BPP seller gateway. |
| `APP_ONDC_BPP_URI` | `http://127.0.0.1:8000/beckn` | Public webhook URI exposed to ONDC buyer network apps. |
| `APP_ONDC_BAP_ID` | `buyer.market.local` | ONDC registered Subscriber ID for logistics BAP client. |
| `APP_ONDC_BAP_URI` | `http://127.0.0.1:8000/beckn/bap` | Public callback URI for incoming LSP quotes and responses. |
| `APP_RUN_WORKERS_INLINE` | `false` | When `true`, runs background workers inside FastAPI web process (dev only). |
| `APP_CHECK_ALEMBIC_HEAD` | `false` | Boot gate verifying database schema matches latest Alembic revision. |
| `APP_MAX_REQUEST_BODY_SIZE_BYTES` | `52428800` (50MB) | Max request payload size (accommodates 8-image multipart assays). |
| `APP_LOG_LEVEL` | `INFO` | Structured JSON log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

---

## 5. Database Migration Workflow

Alembic handles all relational schema alterations, PostGIS geometry types, and TimescaleDB continuous aggregates.

```bash
# 1. Create a new revision after modifying SQLAlchemy models
alembic revision --autogenerate -m "add_new_commodity_metadata"

# 2. Inspect generated migration in alembic/versions/

# 3. Apply migration to local/target database
alembic upgrade head

# 4. Verify database matches latest Alembic head
python -m app.db.alembic_gate
```

---

## 6. Dedicated Worker Daemons

In staging and production, background tasks run as standalone processes decoupled from the web application:

```bash
# 1. AGMARKNET / NDSAP Scheduled Continuous Ingestion Worker
python -m app.workers.ingestion

# 2. Beckn Asynchronous Request-Reply RPC Daemon
python -m app.workers.beckn_rpc

# 3. Transactional Outbox Relay Worker (Postgres Outbox -> Kafka / NATS)
python -m app.workers.outbox_relay

# 4. Price Forecasting TFT Retraining CLI
python -m app.prices.train --commodity Wheat --market "Indore Mandi" --horizons 7,14,21 --publish
```

---

## 7. How to Add a New Commodity

Follow this 5-step checklist to introduce a new agricultural commodity (e.g. *Sunflower* or *Gram*):

### Step 1: Register Commodity in Local Government Directory (LGD)
Add the commodity code, standard English name, Hindi name, and local aliases to `app/prices/lgd_models.py` or seed via `app/api/lgd_admin.py`:
```python
new_commodity = LgdCommodity(
    code="COMM-SUNFLOWER",
    name="Sunflower",
    hindi_name="सूरजमुखी",
    category="OILSEEDS",
    is_active=True,
)
```

### Step 2: Configure Official MSP Schedule & Season
In `app/prices/features/macro.py`, add the Commission for Agricultural Costs and Prices (CACP) Minimum Support Price schedule:
```python
OFFICIAL_MSP_SCHEDULE["Sunflower"] = {
    date(2024, 10, 1): 7280.0,
    date(2025, 10, 1): 7600.0,
    date(2026, 10, 1): 7950.0,
}
```

### Step 3: Configure Quality Assay Classes & Defect Limits
In `app/assay_ai/` and `app/lots/models.py`, register the allowable grade parameters:
- Foreign matter tolerance: $F \le 2.0\%$
- Moisture threshold: $M \le 9.0\%$
- Damaged / weevilled limit: $D \le 3.0\%$

### Step 4: Define Storage Costs & Spoilage Perishability
In `app/prices/recommendations.py`, specify the crop's daily deterioration rate and warehouse profile:
```python
COMMODITY_PERISHABILITY["Sunflower"] = CommodityPerishabilityProfile(
    commodity="Sunflower",
    spoilage_rate_per_day=0.00015,  # 0.015% per day (medium oilseed stability)
    requires_cold_storage=False,
    max_safe_storage_days=180,
    default_storage_charge_inr_per_day=0.60,
)
```

### Step 5: Build Training Frame & Publish ML Forecast Model
Run the forecasting training pipeline to extract 22 continuous daily features, train the quantile pinball TFT model, and publish it to the production registry:
```bash
# Verify feature extraction
python -m app.prices.train --commodity Sunflower --market "Kurnool Mandi" --build-frame

# Run rolling-origin calibration backtest
python -m app.prices.backtest --commodity Sunflower --market "Kurnool Mandi" --seasons 2

# Train and publish to production
python -m app.prices.train --commodity Sunflower --market "Kurnool Mandi" --horizons 7,14,21 --architecture TFT --publish
```

---

## 8. Schema Drift Guard

To guarantee that code modifications do not unintentionally break the Kotlin mobile frontend or partner integrations, run the OpenAPI schema drift guard:

```bash
# Check if live endpoints/schemas match committed baseline
python scripts/check_openapi_drift.py

# Update the committed baseline when changes are intentional
python scripts/check_openapi_drift.py --update
```

---

## 9. Testing & Quality Assurance

Run the comprehensive test suite:
```bash
# Run all unit, integration, and platform tests
python -m pytest -q

# Run dedicated ML forecasting test suite
python -m pytest tests/test_forecast_ml_system.py -v
```

---

## 10. Architecture Decision Records (ADRs)

Key architectural decisions are documented in Markdown Architecture Decision Record (MADR) format under `docs/adr/`:
- [ADR 0001: NATS JetStream and Apache Kafka Hybrid Architecture](docs/adr/0001-nats-kafka-hybrid-architecture.md)
- [ADR 0002: CRDT-Free Sync with Last-Write-Wins (LWW)](docs/adr/0002-crdt-free-sync-with-last-write-wins.md)
- [ADR 0003: Standard Linux Process Isolation Over gVisor Sandboxing](docs/adr/0003-process-isolation-over-gvisor-sandboxing.md)
- [ADR 0004: Unified Order and Trade Contract Model for BAP and BPP Roles](docs/adr/0004-unified-order-model-for-bap-and-bpp.md)
- [ADR 0005: WatermelonDB-Compatible Offline Sync Protocol](docs/adr/0005-watermelondb-compatible-offline-sync-protocol.md)
- [ADR 0006: ONNX Runtime Over TFLite for Server-Side AI Inference](docs/adr/0006-onnx-runtime-over-tflite-for-server-inference.md)
