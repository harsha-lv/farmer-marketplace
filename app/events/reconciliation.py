from typing import Any

from app.events.schemas import AuditReconciliationReport, DivergenceItem


def _normalize_val(val: Any) -> Any:
    if isinstance(val, (int, float)):
        return round(float(val), 2)
    if isinstance(val, str):
        return val.strip()
    return val


def reconcile_audit_ledger(
    stream_id: str,
    reconstructed_state: dict[str, Any],
    projection_state: dict[str, Any] | None,
    event_count: int,
) -> AuditReconciliationReport:
    """Compare point-in-time reconstructed state against current read-model projection and report divergences."""
    entity_type = "TRADE" if stream_id.startswith("trade:") else ("LOT" if stream_id.startswith("lot:") else "GENERIC")

    if projection_state is None:
        return AuditReconciliationReport(
            stream_id=stream_id,
            entity_type=entity_type,
            is_consistent=False,
            event_count=event_count,
            divergences=[
                DivergenceItem(
                    field="entity",
                    reconstructed_value="PRESENT",
                    projected_value="MISSING",
                    discrepancy_type="MISSING_IN_PROJECTION",
                )
            ],
            reconstructed_state=reconstructed_state,
            current_projection_state=None,
            reconciliation_action="REPLAY_REQUIRED",
        )

    divergences: list[DivergenceItem] = []
    # Key comparison fields of interest
    all_keys = set(reconstructed_state.keys()) | set(projection_state.keys())

    # Ignore internal event tracking metadata
    ignored_keys = {"version", "last_modified_at", "last_event_type", "state_hash"}

    for key in sorted(projection_state.keys()):
        if key in ignored_keys:
            continue

        if key not in reconstructed_state:
            divergences.append(
                DivergenceItem(
                    field=key,
                    reconstructed_value=None,
                    projected_value=projection_state[key],
                    discrepancy_type="EXTRA_IN_PROJECTION",
                )
            )
        else:
            val_recon = _normalize_val(reconstructed_state[key])
            val_proj = _normalize_val(projection_state[key])
            if val_recon != val_proj:
                divergences.append(
                    DivergenceItem(
                        field=key,
                        reconstructed_value=reconstructed_state[key],
                        projected_value=projection_state[key],
                        discrepancy_type="VALUE_MISMATCH",
                    )
                )


    is_consistent = len(divergences) == 0

    if is_consistent:
        action = "NO_ACTION_REQUIRED"
    else:
        discrepant_fields = {d.field for d in divergences}
        if "status" in discrepant_fields or "settlement_status" in discrepant_fields:
            action = "REPLAY_REQUIRED"
        else:
            action = "MANUAL_INVESTIGATION"

    return AuditReconciliationReport(
        stream_id=stream_id,
        entity_type=entity_type,
        is_consistent=is_consistent,
        event_count=event_count,
        divergences=divergences,
        reconstructed_state=reconstructed_state,
        current_projection_state=projection_state,
        reconciliation_action=action,
    )
