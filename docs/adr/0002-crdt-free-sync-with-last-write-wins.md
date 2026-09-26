# ADR 0002: CRDT-Free Sync with Last-Write-Wins (LWW) Over Operational CRDTs

- Status: Accepted
- Deciders: Mobile Engineering Team, Backend Data Team
- Date: 2026-09-26

## Context and Problem Statement
FPO field agents and mandis operate in intermittent and offline network environments across rural India. Changes made on mobile devices (e.g. creating farmer profiles, recording harvest lots, logging AI quality assays) must synchronize reliably with the central platform.

We needed to choose between:
1. Operation-based or state-based Conflict-Free Replicated Data Types (CRDTs), such as Yjs or Automerge.
2. Relational delta synchronization with deterministic Last-Write-Wins (LWW) conflict resolution and server-authoritative lifecycle validation.

## Decision Drivers
- **Domain nature**: Agricultural records are discrete relational entities with strict validation invariants (positive numeric weights, LGD geographical codes, non-overlapping land parcels), not collaborative unstructured text documents.
- **Relational integrity**: Relational integrity, foreign keys, and transactional atomicity must be preserved both in edge SQLite and central PostgreSQL.
- **Mobile performance**: Edge devices are budget Android smartphones with constrained CPU, memory, and battery life.
- **Simplicity & Debuggability**: Conflict states must be transparently inspectable by FPO supervisors without complex vector clock mathematics.

## Considered Options
1. **CRDT Tree / Document Model (Yjs / Automerge / Jupyter-style)**: Represent every table or record as a distributed CRDT document.
2. **Relational Delta Sync with Last-Write-Wins (LWW)**: Standard WatermelonDB protocol using high-water mark timestamps (`updated_at`, `device_updated_at`), soft-delete tombstones, and deterministic server-authoritative merge rules.

## Decision Outcome
Chosen option: **Relational Delta Sync with Last-Write-Wins (LWW)**.

- **Record-level LWW**: Conflicts on mutable attributes are resolved by comparing UTC millisecond timestamps (`server_updated_ms > client_updated_ms`).
- **Server-Authoritative Invariants**: Business lifecycle rules take precedence over raw timestamps:
  - Read-only tables (`market_prices`, `facilities`, `trade_contracts`, `consent_artifacts`) cannot be altered by clients.
  - Entities with active pledge liens (`LIEN_MARKED`) or active market listings cannot be deleted by edge clients.
- **UUID Pre-Allocation**: Clients generate cryptographic v4 UUIDs locally; if a duplicate UUID reaches the server, it is merged as an update.

### Positive Consequences
- **Zero CRDT overhead**: No multi-megabyte operation history tombstones or vector clocks stored on mobile devices.
- **Direct SQL mapping**: Edge SQLite and cloud PostgreSQL share identical table structures and column types.
- **Deterministic resolution**: Simple, easily audited resolution rules that business operators can understand.

### Negative Consequences
- True concurrent updates to the same record attribute within the same second resolve in favor of the latest writer, discarding concurrent edits. In practice, FPO field agents are partitioned by village/hub, making concurrent edits to the same lot exceptionally rare.

## Pros and Cons of the Options

### CRDTs (Yjs / Automerge)
- Good: Mathematically guarantees convergence without central server arbitration.
- Bad: Designed for collaborative rich text / JSON trees; awkward fit for relational schemas with foreign key constraints.
- Bad: Exponential storage bloat on mobile SQLite due to operation log tombstones.
- Bad: Cannot enforce transactional cross-table invariants (e.g. lot quantity cannot exceed unpledged inventory).

### Relational LWW (Chosen)
- Good: Lightweight, fast SQLite queries, direct column indexing.
- Good: Allows server to enforce domain-specific validation and legal invariants (DPDP consents, lien freezes).
- Good: Fully compatible with standard mobile libraries (WatermelonDB).
- Bad: Discarded client edits during concurrent modification require client-side notification or resync.
