# ADR 0005: WatermelonDB-Compatible Offline Sync Protocol

- Status: Accepted
- Deciders: Mobile Engineering Team, Backend Data Team
- Date: 2026-09-26

## Context and Problem Statement
FPO field agents and assayers operate in remote mandis and rural farm clusters with intermittent or nonexistent 2G/3G mobile connectivity. Field agents must be able to:
1. Work completely offline (registering farmers, creating commodity lots, recording assays).
2. Perform fast, battery-efficient delta synchronizations when network connectivity is re-established.
3. Handle pagination over large datasets without exhausting mobile memory on entry-level Android smartphones.

We needed a standardized synchronization protocol between the Android Kotlin client and the FastAPI backend.

## Decision Drivers
- **Memory efficiency on low-end hardware**: Field agents use entry-level Android devices (2GB–3GB RAM). Loading thousands of records into mobile memory causes Out-Of-Memory (OOM) crashes.
- **Network bandwidth economy**: Bandwidth is constrained and costly; sync payloads must only transmit changed fields and record IDs (deltas).
- **Client library flexibility**: The protocol must support native Android Kotlin (Room/SQLite) as well as cross-platform mobile frameworks.
- **Pagination & Resumability**: If a network connection drops mid-sync, the client must resume from the last page rather than re-downloading the entire dataset.

## Considered Options
1. **Ad-Hoc REST Endpoints**: Custom per-resource timestamp query endpoints (e.g. `GET /lots?updated_since=...`, `POST /lots/batch`).
2. **GraphQL Subscriptions / Delta Queries**: Use GraphQL queries with delta arguments.
3. **WatermelonDB Sync Protocol**: Standardized two-phase pull/push contract (`GET /sync/pull`, `POST /sync/push`) with table-keyed delta envelopes (`created`, `updated`, `deleted`).

## Decision Outcome
Chosen option: **WatermelonDB-Compatible Offline Sync Protocol**.

- **Phase 1 (`GET /api/v1/sync/pull`)**: The client supplies its `lastPulledAt` high-water mark timestamp. The server returns a structured delta dictionary containing `created`, `updated`, and `deleted` (tombstone IDs) for all synchronized tables, along with a new authoritative server `timestamp`.
- **Phase 2 (`POST /api/v1/sync/push`)**: The client transmits its local changes (`created`, `updated`, `deleted`) along with its previous watermark. The server applies changes, resolves conflicts via LWW, and commits transactionally.
- **Cursor-Based Chunking**: The server supports cursor pagination (`cursor`, `has_more`, `next_cursor`) to partition multi-megabyte syncs into lightweight 500-record chunks.

### Positive Consequences
- **Lazy loading support**: Mobile clients only instantiate objects when rendered in the UI, avoiding mobile memory saturation.
- **Battery & Data efficient**: Minimal wire payload size; zero redundant data transfers.
- **Clear separation of concerns**: The backend exposes a uniform sync contract that can be consumed by Kotlin Room, WatermelonDB, or web dashboards.

### Negative Consequences
- Central server must maintain soft-deletion tombstones (`deleted_at`) across all synchronized tables and enforce periodic 90-day pruning policies.

## Pros and Cons of the Options

### Ad-Hoc REST
- Good: Familiar endpoint design.
- Bad: N+1 HTTP roundtrips across multiple tables (farmers, lots, assays, prices).
- Bad: Lacks cohesive transaction boundary across related records.

### GraphQL
- Good: Flexible client-side field selection.
- Bad: High parsing overhead and battery consumption on mobile CPU.
- Bad: Complex caching and tombstone propagation for deletions.

### WatermelonDB Protocol (Chosen)
- Good: Single HTTP roundtrip transfers all table deltas atomically.
- Good: Built-in tombstone lifecycle for record deletions.
- Good: Standardized, proven architecture for offline-first mobile applications.
- Bad: Requires server-side tracking of creation, update, and deletion timestamps across all participating tables.
