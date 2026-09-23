from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import SessionDep
from app.lots.repository import LotRepository
from app.lots.schemas import LotCreateRequest

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncPushPayload(BaseModel):
    changes: dict[str, dict[str, list[dict[str, Any]]]] = Field(default_factory=dict)
    last_pulled_at: int | None = None


@router.get("")
async def sync_pull(
    session: SessionDep,
    last_pulled_at: int | None = Query(None, alias="lastPulledAt"),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    timestamp = int(now.timestamp())
    since = datetime.fromtimestamp(last_pulled_at, tz=UTC) if last_pulled_at is not None else None

    lot_repo = LotRepository(session)
    lots = await lot_repo.list_modified_since(since)

    lot_records = [
        {
            "id": lot.lot_code,
            "farmer_id": lot.farmer_id,
            "commodity": lot.commodity,
            "variety": lot.variety,
            "quantity_mt": float(lot.quantity_mt),
            "status": lot.status,
            "grade": lot.assay.grade if lot.assay else None,
            "enam_lot_id": lot.enam_lot_id,
            "warehouse_receipt_id": lot.warehouse_receipt_id,
            "created_at": int(lot.created_at.timestamp()),
        }
        for lot in lots
    ]

    return {
        "changes": {
            "inventory_lots": {
                "created": lot_records,
                "updated": [],
                "deleted": [],
            }
        },
        "timestamp": timestamp,
    }


@router.post("")
async def sync_push(
    payload: SyncPushPayload,
    session: SessionDep,
) -> dict[str, Any]:
    lot_repo = LotRepository(session)
    lot_changes = payload.changes.get("inventory_lots", {})
    created_list = lot_changes.get("created", [])
    updated_list = lot_changes.get("updated", [])
    deleted_list = lot_changes.get("deleted", [])

    created_count = 0
    updated_count = 0

    for item in created_list:
        lot_id = str(item.get("id", "")).strip()
        existing = await lot_repo.get(lot_id) if lot_id else None
        if existing is not None:
            # Conflict resolution: record already exists, apply authoritative update
            if "quantity_mt" in item:
                existing.quantity_mt = Decimal(str(item["quantity_mt"]))
            if "variety" in item:
                existing.variety = str(item["variety"]).strip()
            updated_count += 1
        else:
            farmer_id = str(item.get("farmer_id", "")).strip()
            consent_id = str(item.get("consent_artifact_id", "default-consent")).strip()
            commodity = str(item.get("commodity", "")).strip()
            variety = str(item.get("variety", "")).strip()
            quantity = Decimal(str(item.get("quantity_mt", "1")))
            grade = str(item.get("grade", item.get("ai_grade", "FAQ"))).strip()

            if farmer_id and commodity:
                create_req = LotCreateRequest(
                    farmer_id=farmer_id,
                    consent_artifact_id=consent_id,
                    commodity=commodity,
                    variety=variety,
                    quantity_mt=quantity,
                    grade=grade,
                )
                lot = await lot_repo.create(create_req)
                if lot_id and lot_id.startswith("LOT-"):
                    lot.lot_code = lot_id
                created_count += 1

    for item in updated_list:
        lot_id = str(item.get("id", "")).strip()
        if lot_id:
            existing = await lot_repo.get(lot_id)
            if existing is not None:
                if "quantity_mt" in item:
                    existing.quantity_mt = Decimal(str(item["quantity_mt"]))
                if "variety" in item:
                    existing.variety = str(item["variety"]).strip()
                updated_count += 1

    await session.commit()
    return {
        "status": "ok",
        "applied": {
            "created": created_count,
            "updated": updated_count,
            "deleted": len(deleted_list),
        },
    }
