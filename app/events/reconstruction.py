import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.events.schemas import PointInTimeStateResponse


def compute_state_hash(state: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of canonical state dictionary."""

    def _default(val: Any) -> Any:
        if isinstance(val, datetime):
            return val.isoformat()
        return str(val)

    canonical_json = json.dumps(state, sort_keys=True, default=_default)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _reduce_trade(
    state: dict[str, Any],
    event_type: str,
    payload: dict[str, Any],
    occurred_at: datetime,
) -> dict[str, Any]:
    state = dict(state)
    state["last_modified_at"] = occurred_at.isoformat()
    state["version"] = state.get("version", 0) + 1

    if event_type in {"trade.created", "trade.initiated", "TradeContractIssued"}:
        state["trade_id"] = payload.get("trade_id")
        state["buyer_id"] = payload.get("buyer_id")
        state["seller_id"] = payload.get("seller_id")
        state["lot_code"] = payload.get("lot_code")
        state["commodity"] = payload.get("commodity")
        state["quantity_quintals"] = payload.get("quantity_quintals")
        state["price_per_quintal"] = payload.get("price_per_quintal")
        state["total_amount_inr"] = payload.get("total_amount_inr")
        state["status"] = "CONTRACT_ISSUED" if event_type == "TradeContractIssued" else "CREATED"
        state["settlement_status"] = "PENDING"
    elif event_type in {"trade.contract_issued", "TLCGenerated"}:
        state["status"] = "CONTRACT_ISSUED"
        if "contract_id" in payload:
            state["contract_id"] = payload.get("contract_id")
        if "tlc_reference" in payload:
            state["tlc_reference"] = payload.get("tlc_reference")
    elif event_type in {"trade.delivery_scheduled", "ShipmentStatusChanged"}:
        state["status"] = "IN_FULFILLMENT"
        if "fulfillment_id" in payload:
            state["fulfillment_id"] = payload.get("fulfillment_id")
        if "shipment_status" in payload:
            state["shipment_status"] = payload.get("shipment_status")
    elif event_type in {"trade.settled", "settlement.completed", "PaymentSettled", "PaymentEscrowed"}:
        if event_type == "PaymentEscrowed":
            state["settlement_status"] = "ESCROWED"
        else:
            state["status"] = "SETTLED"
            state["settlement_status"] = "COMPLETED"
        if "settlement_id" in payload:
            state["settlement_id"] = payload.get("settlement_id")
        if "payout_ref" in payload:
            state["payout_ref"] = payload.get("payout_ref")
    elif event_type in {"trade.cancelled", "trade.failed"}:
        state["status"] = "CANCELLED"
        state["cancellation_reason"] = payload.get("reason", "Cancelled by user or network")
    else:
        # Merge payload
        for k, v in payload.items():
            state[k] = v

    return state


def _reduce_lot(
    state: dict[str, Any],
    event_type: str,
    payload: dict[str, Any],
    occurred_at: datetime,
) -> dict[str, Any]:
    state = dict(state)
    state["last_modified_at"] = occurred_at.isoformat()
    state["version"] = state.get("version", 0) + 1

    if event_type in {"lot.created", "LotCreated", "GateEntryCreated"}:
        state["lot_code"] = payload.get("lot_code", state.get("lot_code"))
        state["farmer_id"] = payload.get("farmer_id", state.get("farmer_id"))
        state["commodity"] = payload.get("commodity", state.get("commodity"))
        state["quantity_quintals"] = payload.get("quantity_quintals", state.get("quantity_quintals"))
        state["status"] = "GATE_ENTRY" if event_type == "GateEntryCreated" else "CREATED"
        state["pledged"] = False
    elif event_type in {"lot.graded", "LotGraded", "AssayCompleted"}:
        state["status"] = "GRADED"
        if "grade" in payload:
            state["quality_grade"] = payload.get("grade")
        if "moisture_pct" in payload:
            state["moisture_pct"] = payload.get("moisture_pct")
    elif event_type in {"LotListed", "lot.listed"}:
        state["status"] = "LISTED"
    elif event_type in {"LotWithdrawn", "lot.withdrawn"}:
        state["status"] = "WITHDRAWN"
    elif event_type in {"EnwREIssued"}:
        state["enwre_number"] = payload.get("enwre_number")
        state["enwre_issued"] = True
    elif event_type in {"lot.pledged", "PledgeLoanDisbursed"}:
        state["pledged"] = True
        state["loan_id"] = payload.get("loan_id", state.get("loan_id"))
    elif event_type in {"lot.released"}:
        state["pledged"] = False
        state["released_at"] = occurred_at.isoformat()
    else:
        for k, v in payload.items():
            state[k] = v

    return state


def _reduce_generic(
    state: dict[str, Any],
    event_type: str,
    payload: dict[str, Any],
    occurred_at: datetime,
) -> dict[str, Any]:
    state = dict(state)
    state["last_modified_at"] = occurred_at.isoformat()
    state["version"] = state.get("version", 0) + 1
    state["last_event_type"] = event_type
    for k, v in payload.items():
        state[k] = v
    return state


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def reconstruct_point_in_time_state(
    stream_id: str,
    events: Sequence[Any],
    as_of: datetime | None = None,
) -> PointInTimeStateResponse:
    """Fold event stream chronologically up to as_of timestamp to reconstruct point-in-time state."""
    target_as_of = _ensure_utc(as_of)

    # Normalize event items
    normalized: list[tuple[datetime, str, str, dict[str, Any]]] = []
    for e in events:
        if isinstance(e, dict):
            occ_at = e.get("occurred_at")
            if isinstance(occ_at, str):
                occ_at = datetime.fromisoformat(occ_at)
            occ_at = _ensure_utc(occ_at) or datetime.now(UTC)
            normalized.append((occ_at, str(e.get("event_id", "")), e.get("event_type", ""), e.get("payload", {})))
        else:
            raw_occ = getattr(e, "occurred_at", datetime.now(UTC))
            occ_at = _ensure_utc(raw_occ) or datetime.now(UTC)
            evt_id = str(getattr(e, "event_id", getattr(e, "id", "")))
            evt_type = getattr(e, "event_type", "")
            payload = getattr(e, "payload", {})
            normalized.append((occ_at, evt_id, evt_type, payload))

    # Filter events strictly occurred on or before as_of
    eligible = [e for e in normalized if target_as_of is None or e[0] <= target_as_of]
    eligible.sort(key=lambda e: (e[0], e[1]))

    state: dict[str, Any] = {}
    is_trade = stream_id.startswith("trade:") or any(e[2].lower().startswith("trade") or e[2] in {"TradeContractIssued", "PaymentSettled"} for e in eligible)
    is_lot = stream_id.startswith("lot:") or any(e[2].lower().startswith("lot") or e[2] in {"LotCreated", "LotGraded", "AssayCompleted", "LotListed"} for e in eligible)

    for occ_at, evt_id, evt_type, payload in eligible:
        if is_trade:
            state = _reduce_trade(state, evt_type, payload, occ_at)
        elif is_lot:
            state = _reduce_lot(state, evt_type, payload, occ_at)
        else:
            state = _reduce_generic(state, evt_type, payload, occ_at)

    state_hash = compute_state_hash(state)
    return PointInTimeStateResponse(
        stream_id=stream_id,
        as_of=as_of,
        total_events_applied=len(eligible),
        state=state,
        state_hash=state_hash,
    )
