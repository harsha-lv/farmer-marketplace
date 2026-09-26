# ADR 0001: NATS JetStream and Apache Kafka Hybrid Architecture

- Status: Accepted
- Deciders: Backend Architecture Team, Platform Infrastructure
- Date: 2026-09-26

## Context and Problem Statement
The Agri-Market Intelligence Platform serves two fundamentally distinct event streaming workloads:
1. **Long-retention audit and analytical event logs**: High-throughput trade contracts, DPDP compliance outbox relays, and historical mandi price tick feeds requiring multi-month retention and deterministic replay for ML retraining.
2. **Low-latency edge messaging and per-tenant telemetry**: Real-time mandi sensor streams, field device command-and-control, asynchronous Beckn request-reply RPCs, and strict per-FPO queue isolation across hundreds of rural farmer producer organizations.

A single messaging technology cannot optimize for both paradigms without severe operational compromises.

## Decision Drivers
- **Multi-tenancy isolation**: Need lightweight, programmatic creation of dedicated message streams per active FPO without administrative cluster overhead.
- **Compliance & ML Replay**: DPDP Act 2023 requires tamper-evident event streaming with up to 1-year retention; price forecasting ML models require bulk historical replay.
- **Operational footprint**: Resource consumption must be minimal on edge deployments while scaling horizontally in primary cloud regions.
- **Low latency**: Microsecond RPC bridging for ONDC Beckn protocol callbacks and field IoT sensor ingestion.

## Considered Options
1. **Kafka-Only Architecture**: Use Apache Kafka for all streaming, RPC, and telemetry.
2. **NATS JetStream-Only Architecture**: Use NATS JetStream for all event storage, replay, and RPC.
3. **Hybrid Architecture (Kafka + NATS JetStream)**: NATS JetStream for fast multi-tenant edge streams and RPC; Apache Kafka for immutable event outbox persistence, compliance retention, and ML replay.

## Decision Outcome
Chosen option: **Hybrid Architecture (Kafka + NATS JetStream)**.

- **NATS JetStream** powers the operational edge and tenancy tier:
  - Dynamically provisions per-tenant streams (`AGRI_{tenant_id}`) with subject matching (`agri.{tenant_id}.>`).
  - Implements pull-based consumer delivery, flow control, deduplication windows (120s), and dead-letter queues (`AGRI_{tenant_id}_DLQ`).
  - Handles Beckn asynchronous RPC request-reply bridging (`prices.ingest.trigger`, `beckn.request.>`).
- **Apache Kafka** powers the immutable persistence and analytical replay tier:
  - Ingests committed outbox events from PostgreSQL via `TransactionalOutboxRelay`.
  - Maintains 7-day operational retention and 365-day compliance retention topics.
  - Serves as the authoritative replay source for periodic and scheduled ML model retraining.

### Positive Consequences
- Dynamic creation of tenant streams takes milliseconds via NATS API without partition management or topic rebalancing overhead.
- Kafka clusters remain lean, handling partitioned append-only persistence without being burdened by short-lived RPC connections or ephemeral telemetry.
- Zero Kafka consumer lag on operational user-facing requests.

### Negative Consequences
- Two streaming message brokers must be monitored, deployed, and instrumented in cloud environments (mitigated via Prometheus exporters and OpenTelemetry).

## Pros and Cons of the Options

### Kafka-Only
- Good: Single broker ecosystem to operate.
- Bad: Poor support for dynamic multi-tenancy (thousands of small topics degrade ZK/KRaft performance).
- Bad: Lack of native, lightweight request-reply RPC semantics.
- Bad: High resource footprint for small edge deployments.

### NATS-Only
- Good: Ultra-low latency (<1ms), minute memory footprint (<50MB binary), easy per-tenant stream provisioning.
- Bad: Lacks mature ecosystem for distributed analytical stream processing (e.g. Flink/Spark/Kafka Connect).
- Bad: Long-term multi-terabyte tiered storage on object storage is less battle-tested than Kafka's tiered storage.

### Hybrid (Chosen)
- Good: Leverages NATS for what it does best (ephemeral messaging, per-tenant streams, RPC).
- Good: Leverages Kafka for what it does best (high-throughput append logs, long retention, analytical replay).
- Bad: Dual broker operational management.
