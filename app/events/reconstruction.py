from datetime import datetime
import hashlib
import json
from typing import Any, Sequence

from app.events.models import OutboxEvent
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

    if event_type in {"trade.created", "trade.initiated"}:
        state["trade_id"] = payload.get("trade_id")
        state["buyer_id"] = payload.get("buyer_id")
        state["seller_id"] = payload.get("seller_id")
        state["lot_code"] = payload.get("lot_code")
        state["commodity"] = payload.get("commodity")
        state["quantity_quintals"] = payload.get("quantity_quintals")
        state["price_per_quintal"] = payload.get("price_per_quintal")
        state["total_amount_inr"] = payload.get("total_amount_inr")
        state["status"] = "CREATED"
        state["settlement_status"] = "PENDING"
    elif event_type == "trade.contract_issued":
        state["status"] = "CONTRACT_ISSUED"
        state["contract_id"] = payload.get("contract_id")
        state["contract_hash"] = payload.get("contract_hash")
    elif event_type == "trade.delivery_scheduled":
        state["status"] = "IN_FULFILLMENT"
        state["fulfillment_id"] = payload.get("fulfillment_id")
        state["scheduled_date"] = payload.get("scheduled_date")
    elif event_type in {"trade.settled", "settlement.completed"}:
        state["status"] = "SETTLED"
        state["settlement_status"] = "COMPLETED"
        state["settlement_id"] = payload.get("settlement_id")
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

    if event_type == "lot.created":
        state["lot_code"] = payload.get("lot_code")
        state["farmer_id"] = payload.get("farmer_id")
        state["commodity"] = payload.get("commodity")
        state["quantity_quintals"] = payload.get("quantity_quintals")
        state["status"] = "CREATED"
        state["pledged"] = False
    elif event_type == "lot.graded":
        state["status"] = "GRADED"
        state["quality_grade"] = payload.get("grade")
        state["moisture_pct"] = payload.get("moisture_pct")
    elif event_type == "lot.pledged":
        state["pledged"] = True
        state["loan_id"] = payload.get("loan_id")
    elif event_type == "lot.released":
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


def reconstruct_point_in_time_state(
    stream_id: str,
    events: Sequence[OutboxEvent],
    as_of: datetime | None = None,
) -> PointInTimeStateResponse:
    """Fold event stream chronologically up to as_of timestamp to reconstruct point-in-time state."""
    # Filter events strictly occurred on or before as_of
    eligible = [e for e in events if as_of is None or e.occurred_at <= as_of]
    eligible.sort(key=lambda e: (e.occurred_at, e.id))

    state: dict[str, Any] = {}
    is_trade = stream_id.startswith("trade:") or any(e.event_type.startswith("trade.") for e in eligible)
    is_lot = stream_id.startswith("lot:") or any(e.event_type.startswith("lot.") for e in eligible)

    for event in eligible:
        if is_trade:
            state = _reduce_trade(state, event.event_type, event.payload, event.occurred_at)
        elif is_lot:
            state = _reduce_lot(state, event.event_type, event.payload, event.occurred_at)
        else:
            state = _reduce_generic(state, event.event_type, event.payload, event.occurred_at)

    state_hash = compute_state_hash(state)
    return PointInTimeStateResponse(
        stream_id=stream_id,
        as_of=as_of,
        total_events_applied=len(eligible),
        state=state,
        state_hash=state_hash,
    )
