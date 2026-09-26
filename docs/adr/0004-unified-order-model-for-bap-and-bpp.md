# ADR 0004: Unified Order and Trade Contract Model for BAP and BPP Roles

- Status: Accepted
- Deciders: ONDC Integration Team, Core Domain Architecture
- Date: 2026-09-26

## Context and Problem Statement
Under the Open Network for Digital Commerce (ONDC) Beckn protocol specifications:
1. The platform acts as a **Beckn Provider (BPP)** when exposing farmer commodity inventory and catalog lots to network buyers.
2. The platform acts as a **Beckn Application (BAP)** when querying, selecting, and confirming third-party Logistics Service Providers (LSPs) to transport traded commodities.

We needed to decide whether to maintain two disjoint order and fulfillment models (`bpp_orders` vs `bap_orders`) or build a unified order and contract lifecycle.

## Decision Drivers
- **Domain continuum**: A physical trade begins as a BPP commodity sale and immediately triggers a BAP logistics dispatch for the exact same physical commodity lot.
- **Traceability & Auditing**: End-to-end provenance requires tracing a farmer's lot code, buyer payment, warehouse release, and LSP tracking URL within a cohesive data lineage.
- **Protocol parity**: Beckn protocol payloads for order confirmation, quote breakdown, and fulfillment tracking share identical JSON schemas across domains.
- **Code reuse**: Shared logic for tax deduction at source (TDS), commission calculation, e-RUPI vouchers, and Issue & Grievance Management (IGM).

## Considered Options
1. **Split Models (`bpp_orders` and `bap_orders`)**: Two separate domain models and database tables, with an external correlation mapping table.
2. **Unified Order & Trade Contract Model**: A single unified trade and order model (`TradeContract`, `Shipment`, `BapQuote`) that represents the composite transaction, with explicit role semantics (`BPP_SELLER`, `BAP_BUYER`).

## Decision Outcome
Chosen option: **Unified Order & Trade Contract Model**.

- **Core Contract Entity (`TradeContract`)**: Encapsulates the economic agreement, agreed modal price, commission, settlement hold, and buyer/seller identities.
- **Fulfillment Entity (`Shipment`)**: Encapsulates the physical logistics leg, connecting internal PostGIS routing or external ONDC LSP quotes (`bap_quote_id`, `carrier_tracking_url`, `delivery_status`).
- **Beckn Protocol Mapping**: BPP requests (`/on_search`, `/select`, `/confirm`) populate and advance the contract; BAP logistics client actions (`/beckn/bap/select`, `/confirm`) update the linked shipment.

### Positive Consequences
- Seamless end-to-end transaction lifecycle without dual-write synchronization bugs.
- Single source of truth for financial settlements and dispute management (IGM).
- Unified outbox events emitted to Kafka/NATS (`trade.confirmed`, `shipment.dispatched`, `shipment.delivered`).

### Negative Consequences
- Schema must support nullable fields for transactions that use internal FPO logistics rather than external ONDC LSPs.

## Pros and Cons of the Options

### Split Models
- Good: Total isolation between logistics BAP code and marketplace BPP code.
- Bad: Complex distributed transactions to synchronize logistics failure back to trade cancellation.
- Bad: Duplicate code for Beckn signature validation, quote formatting, and currency conversion.

### Unified Model (Chosen)
- Good: Natural representation of real-world physical agriculture: a trade requires a shipment.
- Good: Atomic database updates for contract and fulfillment state.
- Good: Simpler reporting for FPO administrators and bank auditors.
- Bad: Slightly larger model surface area.
