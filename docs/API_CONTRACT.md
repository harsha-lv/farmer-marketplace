# Agri-Market Intelligence Platform: API Contract & Frontend Integration Guide

This document is the **single source of truth** for the Android (Kotlin) mobile development team, Web dashboard engineers, and external partner integrations.

---

## 1. System Overview & Gateway Environments

### 1.1 Base URLs
| Environment | Base URL | Purpose |
|:---|:---|:---|
| **Local Development** | `http://localhost:8000` | Local Docker compose / venv instance |
| **Staging (Pre-Prod)** | `https://staging-api.agrimarket.local` | ONDC pre-production testbed & QA |
| **Production** | `https://api.agrimarket.local` | Live production gateway |
| **ONDC Beckn BPP** | `https://api.agrimarket.local/beckn` | Inbound ONDC buyer network gateway |

### 1.2 Required Client Headers
Every HTTP request from the Kotlin client must provide standard headers:
```http
Authorization: Bearer <jwt_access_token>
X-Request-ID: <client-generated-uuid4>
X-Timestamp: 2026-09-26T00:30:00.000Z
Content-Type: application/json
Accept: application/json
```
For mutating operations requiring idempotency (trades, lot creation, loan disbursement):
```http
X-Idempotency-Key: <unique-client-mutation-key>
```

---

## 2. Authentication, Tokens & RBAC Matrix

### 2.1 Authentication Flow
The platform implements OAuth2 password flow with asymmetric access & refresh token pairs.

#### 1. Login (`POST /api/v1/auth/token`)
- **Content-Type**: `application/x-www-form-urlencoded`
- **Request Body**:
  ```
  username=fpo_operator_indore&password=SecurePassword123!
  ```
- **Response (`TokenResponse`)** (HTTP 200):
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "d7a8b4c2e1f0...",
    "token_type": "bearer",
    "expires_in_seconds": 900,
    "user": {
      "user_id": "usr-8891-2026",
      "username": "fpo_operator_indore",
      "roles": ["fpo_operator"],
      "org_id": "FPO-MALWA-01",
      "display_name": "Ramesh Patel"
    }
  }
  ```

#### 2. Refresh Token (`POST /api/v1/auth/refresh`)
- **Request Body**:
  ```json
  {
    "refresh_token": "d7a8b4c2e1f0..."
  }
  ```
- **Response** (HTTP 200): Returns fresh `access_token` (valid for 15 minutes).

### 2.2 Role-Based Access Control (RBAC) Matrix

| Endpoint Group | Required Role(s) | Description |
|:---|:---|:---|
| `/api/v1/farmers/**` | `fpo_operator`, `admin` | Create/update farmer records, KYC, land parcels. |
| `/api/v1/lots/create`, `/update` | `farmer`, `fpo_operator` | Register harvest commodity lots. |
| `/api/v1/assay/**` | `assayer`, `fpo_operator` | Upload images, run AI quality scoring, HMAC signing. |
| `/api/v1/trades/offer`, `/accept` | `buyer`, `fpo_operator` | Execute bilateral trades and counter-offers. |
| `/api/v1/finance/pledge/**` | `bank`, `fpo_operator` | Apply for e-NWR warehouse pledge loans, mark liens. |
| `/api/v1/sync/**` | Any authenticated user | WatermelonDB offline-first delta synchronization. |
| `/api/v1/prices/**` | Open / Authenticated | Mandi price intelligence & TFT ML price forecasts. |
| `/api/v1/logistics/**` | `fpo_operator`, `buyer`, `logistics` | Haulage routing, LSP quotes, and dispatch confirmation. |
| `/api/v1/grievances/**` | Any authenticated user | ONDC IGM dispute tickets and respondent resolution. |
| `/api/v1/admin-lgd/**` | `admin` | Local Government Directory (LGD) reconciliation. |

---

## 3. Standard Conventions: Pagination, Sorting & Errors

### 3.1 Pagination & Sorting
All list endpoints conform to the following query parameters:
- `page`: 1-indexed page number (default: `1`).
- `page_size`: Number of records per page (default: `20`, max: `100`).
- `sort_by`: Field name to sort on (e.g. `observed_at`, `created_at`).
- `order`: Sort order (`asc` or `desc`, default: `desc`).

**Standard Enveloped Response**:
```json
{
  "items": [ ... ],
  "total": 154,
  "page": 1,
  "page_size": 20,
  "pages": 8
}
```

### 3.2 Standard Error Response Shape
All 4xx and 5xx responses emit a standardized JSON envelope:
```json
{
  "error": {
    "code": "LOT_ALREADY_LOCKED",
    "message": "Cannot modify or re-assay lot 'LOT-IND-2026-0012' because it is locked in an active trade negotiation.",
    "details": {
      "lot_code": "LOT-IND-2026-0012",
      "active_contract_code": "TRD-2026-0981"
    }
  },
  "request_id": "req-9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "timestamp": "2026-09-26T00:30:00Z"
}
```

#### Standard Error Code Dictionary
| Error Code | HTTP Status | Description |
|:---|:---|:---|
| `AUTH_INVALID_CREDENTIALS` | 401 | Incorrect username or password. |
| `TOKEN_EXPIRED` | 401 | Access token expired. Call `/auth/refresh`. |
| `FORBIDDEN_ROLE` | 403 | User role lacks authorization for this endpoint. |
| `RESOURCE_NOT_FOUND` | 404 | Entity ID does not exist. |
| `CONSENT_REVOKED` | 403 | Farmer DPDP consent has been revoked or expired. |
| `LOT_ALREADY_LOCKED` | 409 | Commodity lot is locked in trade escrow or warehouse lien. |
| `LIEN_MARKED_CANNOT_DELETE`| 409 | Lot has an active bank pledge loan lien. |
| `HMAC_VERIFICATION_FAILED` | 400 | Quality assay HMAC signature does not match payload. |
| `VALIDATION_ERROR` | 422 | Schema validation failed on input parameters. |
| `INTERNAL_SERVER_ERROR` | 500 | Unhandled system exception with correlated `request_id`. |

---

## 4. Core Domain Payload Contracts (Kotlin Data Shapes)

### 4.1 Commodity Lots (`/api/v1/lots`)

#### Lifecycle State Machine
$$\text{DRAFT} \longrightarrow \text{REGISTERED} \longrightarrow \text{ASSAYED} \longrightarrow \text{LISTED} \longrightarrow \text{LOCKED} \longrightarrow \text{TRADED}$$

#### 1. Create Lot (`POST /api/v1/lots`)
```json
{
  "farmer_id": "FARMER-MP-001",
  "commodity": "Wheat",
  "variety": "Sharbati",
  "quantity_mt": 12.5,
  "consent_artifact_id": "CA-8891-2026",
  "enam_lot_id": null,
  "warehouse_receipt_id": null
}
```

#### 2. Lot Response (`LotResponse`)
```json
{
  "lot_code": "LOT-IND-2026-0012",
  "farmer_id": "FARMER-MP-001",
  "commodity": "Wheat",
  "variety": "Sharbati",
  "quantity_mt": 12.5,
  "status": "REGISTERED",
  "consent_artifact_id": "CA-8891-2026",
  "enam_lot_id": null,
  "warehouse_receipt_id": null,
  "org_id": "FPO-MALWA-01",
  "created_at": "2026-09-26T00:10:00Z",
  "updated_at": "2026-09-26T00:10:00Z"
}
```

---

### 4.2 AI Quality Assay (`/api/v1/assay`)

#### 1. Run Assay Inspection (`POST /api/v1/assay/inspect`)
- **Content-Type**: `multipart/form-data`
- **Form Fields**:
  - `lot_code`: `LOT-IND-2026-0012`
  - `commodity`: `Wheat`
  - `variety`: `Sharbati`
  - `images`: 1 to 8 image files (`image/jpeg` or `image/png`)

#### 2. Assay Response (`AssayReportResponse`)
```json
{
  "assay_id": "ASSAY-LOT-IND-2026-0012",
  "lot_code": "LOT-IND-2026-0012",
  "commodity": "Wheat",
  "variety": "Sharbati",
  "grade": "Grade A",
  "confidence_score": 0.942,
  "parameters": {
    "moisture_percent": 11.4,
    "foreign_matter_percent": 0.8,
    "damaged_percent": 1.2,
    "immature_percent": 0.5,
    "weevilled_percent": 0.0
  },
  "tamper_evident_hmac": "3a8f9c1e4d7b2a0f8e9c...",
  "assayed_by": "usr-8891-2026",
  "assayed_at": "2026-09-26T00:15:00Z"
}
```

---

### 4.3 Bilateral Trade Contracts (`/api/v1/trades`)

#### 1. Propose Trade Offer (`POST /api/v1/trades`)
```json
{
  "lot_code": "LOT-IND-2026-0012",
  "buyer_name": "ITC Agri-Business Division",
  "offered_price_inr_per_quintal": 2550.0,
  "quantity_mt": 12.5,
  "delivery_location": "Pithampur Warehouse Hub",
  "terms": "Ex-Warehouse, payment on physical verification"
}
```

#### 2. Trade Contract Response (`TradeContractResponse`)
```json
{
  "contract_code": "TRD-2026-0981",
  "transaction_id": "txn-550e8400-e29b-41d4-a716-446655440000",
  "lot_code": "LOT-IND-2026-0012",
  "farmer_id": "FARMER-MP-001",
  "buyer_name": "ITC Agri-Business Division",
  "quantity_mt": 12.5,
  "price_inr": 318750.0,
  "commission_inr": 3187.5,
  "status": "OFFERED",
  "settlement_hold": false,
  "created_at": "2026-09-26T00:20:00Z",
  "updated_at": "2026-09-26T00:20:00Z"
}
```

---

### 4.4 Mandi Prices & TFT ML Forecasting (`/api/v1/prices`)

#### 1. Real-Time Mandi Quotes (`GET /api/v1/prices/observations`)
- **Query**: `?commodity=Wheat&market=Indore%20Mandi`
- **Response**:
```json
[
  {
    "id": 10842,
    "commodity": "Wheat",
    "market": "Indore Mandi",
    "district": "Indore",
    "state": "Madhya Pradesh",
    "modal_price": 2420.0,
    "min_price": 2350.0,
    "max_price": 2540.0,
    "arrivals_volume": 120.5,
    "observed_at": "2026-09-25T14:30:00Z"
  }
]
```

#### 2. Versioned ML Forecast & Recommendations (`GET /api/v1/prices/forecast/ml`)
- **Query**: `?commodity=Wheat&market=Indore%20Mandi`
- **Response (`MlForecastResponse`)**:
```json
{
  "commodity": "Wheat",
  "market": "Indore Mandi",
  "as_of_date": "2026-09-26",
  "current_modal_price_inr": 2420.0,
  "model_version": "wheat_indore_mandi_tft_20260925185121_bca97d",
  "model_architecture": "TFT",
  "model_status": "PRODUCTION",
  "fallback_used": null,
  "overall_recommendation": "STORE",
  "rationale": "Strong upward price trajectory projected over 14-21 days outpacing Rs 0.50/qtl storage and carrying costs.",
  "facility_available": true,
  "horizons": [
    {
      "horizon_days": 7,
      "p10_price_inr": 2435.0,
      "p50_price_inr": 2465.0,
      "p90_price_inr": 2498.0,
      "storage_cost_inr": 3.5,
      "carrying_interest_inr": 3.25,
      "spoilage_risk_cost_inr": 1.7,
      "expected_net_gain_inr": 36.55,
      "recommendation": "STORE"
    },
    {
      "horizon_days": 14,
      "p10_price_inr": 2470.0,
      "p50_price_inr": 2520.0,
      "p90_price_inr": 2575.0,
      "storage_cost_inr": 7.0,
      "carrying_interest_inr": 6.5,
      "spoilage_risk_cost_inr": 3.39,
      "expected_net_gain_inr": 83.11,
      "recommendation": "STORE"
    },
    {
      "horizon_days": 21,
      "p10_price_inr": 2505.0,
      "p50_price_inr": 2580.0,
      "p90_price_inr": 2660.0,
      "storage_cost_inr": 10.5,
      "carrying_interest_inr": 9.76,
      "spoilage_risk_cost_inr": 5.08,
      "expected_net_gain_inr": 134.66,
      "recommendation": "STORE"
    }
  ]
}
```

---

## 5. Offline-First WatermelonDB Sync Contract

Field Android devices synchronize data via two endpoints:
- `GET /api/v1/sync/pull?lastPulledAt=<epoch_ms>&limit=500`
- `POST /api/v1/sync/push`

For detailed table mappings, conflict resolution rules (LWW), tombstone lifecycles, and cursor pagination rules, refer directly to:
👉 [SYNC_CONTRACT.md](file:///e:/projects/farmer-marketplace/SYNC_CONTRACT.md)

---

## 6. ONDC Beckn Protocol & Webhook Callbacks

### 6.1 BPP (Seller Gateway) Inbound Callbacks
When external ONDC BAPs interact with this platform:
1. **Synchronous ACK**:
   Every inbound Beckn request (`/search`, `/select`, `/init`, `/confirm`, `/status`, `/track`, `/cancel`) receives an immediate synchronous ACK:
   ```json
   {
     "message": {
       "ack": {
         "status": "ACK"
       }
     }
   }
   ```
2. **Asynchronous Callback**:
   Within 1000ms, the platform dispatches the result to the caller's `bap_uri` (e.g. `POST {bap_uri}/on_search`).
   - The outbound request includes an HTTP `Authorization` header containing an Ed25519 digital signature generated over the request body and Blake2b digest.

### 6.2 BAP Logistics Network Quote Aggregation
When the platform acts as a BAP to procure delivery for a trade:
1. **Request Network Quotes (`POST /api/v1/logistics/quote`)**:
   Sends asynchronous Beckn `/search` to ONDC Logistics BPPs with pickup/drop GPS coordinates, weight, vehicle type, and cold-chain flags.
2. **Aggregated Freight Quote (`FreightQuote`)**:
   ```json
   {
     "quote_id": "QUO-ONDC-LSP-091",
     "lsp_id": "delhivery.logistics.bpp",
     "lsp_name": "Delhivery Freight",
     "total_price_inr": 4850.0,
     "eta_hours": 36,
     "vehicle_type": "10_TON_TRUCK",
     "cold_chain": false,
     "internal_estimate_inr": 5120.0,
     "valid_until": "2026-09-26T12:00:00Z"
   }
   ```
3. **LSP Tracking Webhooks (`POST /api/v1/logistics/webhooks/{lsp_id}`)**:
   LSPs push async status (`INIT -> IN_TRANSIT -> OUT_FOR_DELIVERY -> DELIVERED`) and live GPS coordinates directly to this endpoint.
