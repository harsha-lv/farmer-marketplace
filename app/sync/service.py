"""WatermelonDB offline-first synchronization engine with deterministic conflict resolution."""

import base64
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.schemas import UserContext
from app.consent.models import ConsentArtifact
from app.farmers.models import Farmer, LandParcel
from app.finance.models import PledgeLoan
from app.logistics.models import Facility
from app.lots.models import AssayReport, Lot
from app.prices.models import Commodity, Market, PriceObservation
from app.sync.models import BuyerDemand
from app.sync.schemas import (
    ColumnSchema,
    ConflictItem,
    SyncPullResponse,
    SyncPushPayload,
    SyncPushResponse,
    SyncSchemaResponse,
    TableChanges,
    TableSchema,
)
from app.trades.models import TradeContract

logger = logging.getLogger("app.sync.service")

SYNC_TABLES = [
    "farmers",
    "land_parcels",
    "lots",
    "assay_reports",
    "buyer_demand",
    "market_prices",
    "inventory_lots",
    "facilities",
    "trade_contracts",
    "consent_artifacts",
]

READ_ONLY_TABLES = {"market_prices", "trade_contracts", "consent_artifacts", "facilities"}


def ms_to_dt(ms: int | None) -> datetime | None:
    if ms is None or ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC)


def dt_to_ms(dt: Any | None) -> int | None:
    if dt is None:
        return None
    if isinstance(dt, (int, float)):
        return int(dt)
    if isinstance(dt, str):
        try:
            clean = dt.strip().replace(" ", "T")
            parsed = datetime.fromisoformat(clean)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return int(parsed.timestamp() * 1000)
        except (ValueError, TypeError, AttributeError):
            return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp() * 1000)
    return None


class SyncService:
    """Implements canonical WatermelonDB pull, push, delta computation, and conflict resolution."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def get_schema(self) -> SyncSchemaResponse:
        """Return the exact schema structure for all synchronized tables."""
        tables: dict[str, TableSchema] = {
            "farmers": TableSchema(
                mode="read_write",
                primary_key="id",
                columns=[
                    ColumnSchema(name="id", type="string", nullable=False, primary_key=True),
                    ColumnSchema(name="farmer_id", type="string", nullable=False),
                    ColumnSchema(name="display_name", type="string", nullable=False),
                    ColumnSchema(name="state_lgd_code", type="string", nullable=False),
                    ColumnSchema(name="consent_artifact_id", type="string", nullable=False),
                    ColumnSchema(name="org_id", type="string", nullable=True),
                    ColumnSchema(name="created_at", type="number", nullable=False),
                    ColumnSchema(name="updated_at", type="number", nullable=False),
                    ColumnSchema(name="deleted_at", type="number", nullable=True),
                ],
            ),
            "land_parcels": TableSchema(
                mode="read_write",
                primary_key="id",
                columns=[
                    ColumnSchema(name="id", type="string", nullable=False, primary_key=True),
                    ColumnSchema(name="farmer_id", type="string", nullable=False),
                    ColumnSchema(name="farm_id", type="string", nullable=False),
                    ColumnSchema(name="area_hectares", type="number", nullable=True),
                    ColumnSchema(name="created_at", type="number", nullable=False),
                    ColumnSchema(name="updated_at", type="number", nullable=False),
                    ColumnSchema(name="deleted_at", type="number", nullable=True),
                ],
            ),
            "lots": TableSchema(
                mode="read_write",
                primary_key="id",
                columns=[
                    ColumnSchema(name="id", type="string", nullable=False, primary_key=True),
                    ColumnSchema(name="farmer_id", type="string", nullable=False),
                    ColumnSchema(name="commodity", type="string", nullable=False),
                    ColumnSchema(name="variety", type="string", nullable=False),
                    ColumnSchema(name="quantity_mt", type="number", nullable=False),
                    ColumnSchema(name="status", type="string", nullable=False),
                    ColumnSchema(name="consent_artifact_id", type="string", nullable=False),
                    ColumnSchema(name="enam_lot_id", type="string", nullable=True),
                    ColumnSchema(name="warehouse_receipt_id", type="string", nullable=True),
                    ColumnSchema(name="org_id", type="string", nullable=True),
                    ColumnSchema(name="created_at", type="number", nullable=False),
                    ColumnSchema(name="updated_at", type="number", nullable=False),
                    ColumnSchema(name="deleted_at", type="number", nullable=True),
                ],
            ),
            "assay_reports": TableSchema(
                mode="read_write",
                primary_key="id",
                columns=[
                    ColumnSchema(name="id", type="string", nullable=False, primary_key=True),
                    ColumnSchema(name="lot_id", type="string", nullable=False),
                    ColumnSchema(name="grade", type="string", nullable=False),
                    ColumnSchema(name="moisture_percent", type="number", nullable=True),
                    ColumnSchema(name="foreign_matter_percent", type="number", nullable=True),
                    ColumnSchema(name="damaged_percent", type="number", nullable=True),
                    ColumnSchema(name="recorded_at", type="number", nullable=False),
                    ColumnSchema(name="created_at", type="number", nullable=False),
                    ColumnSchema(name="updated_at", type="number", nullable=False),
                    ColumnSchema(name="deleted_at", type="number", nullable=True),
                ],
            ),
            "buyer_demand": TableSchema(
                mode="read_write",
                primary_key="id",
                columns=[
                    ColumnSchema(name="id", type="string", nullable=False, primary_key=True),
                    ColumnSchema(name="buyer_id", type="string", nullable=False),
                    ColumnSchema(name="commodity", type="string", nullable=False),
                    ColumnSchema(name="variety", type="string", nullable=True),
                    ColumnSchema(name="target_grade", type="string", nullable=True),
                    ColumnSchema(name="quantity_mt", type="number", nullable=False),
                    ColumnSchema(name="target_price_per_mt", type="number", nullable=True),
                    ColumnSchema(name="delivery_location", type="string", nullable=True),
                    ColumnSchema(name="status", type="string", nullable=False),
                    ColumnSchema(name="org_id", type="string", nullable=True),
                    ColumnSchema(name="created_at", type="number", nullable=False),
                    ColumnSchema(name="updated_at", type="number", nullable=False),
                    ColumnSchema(name="deleted_at", type="number", nullable=True),
                ],
            ),
            "inventory_lots": TableSchema(
                mode="read_write",
                primary_key="id",
                columns=[
                    ColumnSchema(name="id", type="string", nullable=False, primary_key=True),
                    ColumnSchema(name="farmer_id", type="string", nullable=False),
                    ColumnSchema(name="commodity", type="string", nullable=False),
                    ColumnSchema(name="variety", type="string", nullable=False),
                    ColumnSchema(name="quantity_mt", type="number", nullable=False),
                    ColumnSchema(name="status", type="string", nullable=False),
                    ColumnSchema(name="grade", type="string", nullable=True),
                    ColumnSchema(name="warehouse_id", type="string", nullable=True),
                    ColumnSchema(name="warehouse_receipt_id", type="string", nullable=True),
                    ColumnSchema(name="created_at", type="number", nullable=False),
                    ColumnSchema(name="updated_at", type="number", nullable=False),
                    ColumnSchema(name="deleted_at", type="number", nullable=True),
                ],
            ),
            "facilities": TableSchema(
                mode="read_only",
                primary_key="id",
                columns=[
                    ColumnSchema(name="id", type="string", nullable=False, primary_key=True),
                    ColumnSchema(name="name", type="string", nullable=False),
                    ColumnSchema(name="facility_type", type="string", nullable=False),
                    ColumnSchema(name="state", type="string", nullable=False),
                    ColumnSchema(name="district", type="string", nullable=False),
                    ColumnSchema(name="capacity_quintals", type="number", nullable=False),
                    ColumnSchema(name="available_quintals", type="number", nullable=False),
                    ColumnSchema(name="cold_storage", type="boolean", nullable=False),
                    ColumnSchema(name="daily_charge_inr_per_quintal", type="number", nullable=False),
                    ColumnSchema(name="created_at", type="number", nullable=False),
                    ColumnSchema(name="updated_at", type="number", nullable=False),
                    ColumnSchema(name="deleted_at", type="number", nullable=True),
                ],
            ),
            "market_prices": TableSchema(
                mode="read_only",
                primary_key="id",
                columns=[
                    ColumnSchema(name="id", type="string", nullable=False, primary_key=True),
                    ColumnSchema(name="commodity", type="string", nullable=False),
                    ColumnSchema(name="market_name", type="string", nullable=False),
                    ColumnSchema(name="state", type="string", nullable=False),
                    ColumnSchema(name="modal_price_inr", type="number", nullable=False),
                    ColumnSchema(name="min_price_inr", type="number", nullable=False),
                    ColumnSchema(name="max_price_inr", type="number", nullable=False),
                    ColumnSchema(name="observation_date", type="string", nullable=False),
                    ColumnSchema(name="updated_at", type="number", nullable=False),
                ],
            ),
            "trade_contracts": TableSchema(
                mode="read_only",
                primary_key="id",
                columns=[
                    ColumnSchema(name="id", type="string", nullable=False, primary_key=True),
                    ColumnSchema(name="transaction_id", type="string", nullable=False),
                    ColumnSchema(name="lot_code", type="string", nullable=False),
                    ColumnSchema(name="farmer_id", type="string", nullable=False),
                    ColumnSchema(name="buyer_name", type="string", nullable=False),
                    ColumnSchema(name="quantity_mt", type="number", nullable=False),
                    ColumnSchema(name="price_inr", type="number", nullable=False),
                    ColumnSchema(name="commission_inr", type="number", nullable=False),
                    ColumnSchema(name="status", type="string", nullable=False),
                    ColumnSchema(name="settlement_hold", type="boolean", nullable=False),
                    ColumnSchema(name="created_at", type="number", nullable=False),
                    ColumnSchema(name="updated_at", type="number", nullable=False),
                    ColumnSchema(name="deleted_at", type="number", nullable=True),
                ],
            ),
            "consent_artifacts": TableSchema(
                mode="read_only",
                primary_key="id",
                columns=[
                    ColumnSchema(name="id", type="string", nullable=False, primary_key=True),
                    ColumnSchema(name="farmer_id", type="string", nullable=False),
                    ColumnSchema(name="purpose", type="string", nullable=False),
                    ColumnSchema(name="status", type="string", nullable=False),
                    ColumnSchema(name="expires_at", type="number", nullable=False),
                    ColumnSchema(name="created_at", type="number", nullable=False),
                    ColumnSchema(name="updated_at", type="number", nullable=False),
                    ColumnSchema(name="deleted_at", type="number", nullable=True),
                ],
            ),
        }
        return SyncSchemaResponse(schema_version=1, migration_version=1, tables=tables)

    async def pull(
        self,
        user_ctx: UserContext,
        last_pulled_at: int | None = None,
        limit: int = 500,
        cursor: str | None = None,
        schema_version: int = 1,
        migration_version: int = 1,
    ) -> SyncPullResponse:
        """Compute delta changes per table since lastPulledAt with pagination and tenant isolation."""
        now = datetime.now(UTC)
        new_last_pulled_at = int(now.timestamp() * 1000)
        since_dt = ms_to_dt(last_pulled_at)
        limit = min(max(int(limit), 1), 2000)

        # Parse continuation cursor if supplied: format table_name:offset
        start_table = None
        start_offset = 0
        if cursor:
            try:
                decoded = base64.b64decode(cursor.encode("ascii")).decode("utf-8")
                parts = decoded.split(":")
                if len(parts) == 2:
                    start_table = parts[0]
                    start_offset = int(parts[1])
            except (ValueError, TypeError, UnicodeDecodeError):
                start_table = None
                start_offset = 0

        changes: dict[str, TableChanges] = {t: TableChanges() for t in SYNC_TABLES}
        total_records_collected = 0
        has_more = False
        next_cursor = None

        skip_until_start = start_table is not None

        for table in SYNC_TABLES:
            if skip_until_start:
                if table != start_table:
                    continue
                skip_until_start = False
                offset = start_offset
            else:
                offset = 0

            available_limit = limit - total_records_collected
            if available_limit <= 0:
                has_more = True
                next_cursor = base64.b64encode(f"{table}:{offset}".encode()).decode("ascii")
                break

            tbl_changes, count, tbl_has_more = await self._pull_table(
                table=table,
                user_ctx=user_ctx,
                since_dt=since_dt,
                limit=available_limit,
                offset=offset,
                last_pulled_at=last_pulled_at,
            )
            changes[table] = tbl_changes
            total_records_collected += count

            if tbl_has_more:
                has_more = True
                next_cursor = base64.b64encode(f"{table}:{offset + count}".encode()).decode("ascii")
                break

        return SyncPullResponse(
            changes=changes,
            newLastPulledAt=new_last_pulled_at,
            migrationVersion=migration_version,
            schemaVersion=schema_version,
            hasMore=has_more,
            cursor=next_cursor,
        )

    async def _pull_table(
        self,
        table: str,
        user_ctx: UserContext,
        since_dt: datetime | None,
        limit: int,
        offset: int = 0,
        last_pulled_at: int | None = None,
    ) -> tuple[TableChanges, int, bool]:
        created: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []
        deleted: list[str] = []

        org_id = user_ctx.org_id

        if table == "farmers":
            stmt = select(Farmer)
            if org_id:
                stmt = stmt.where(or_(Farmer.org_id == org_id, Farmer.org_id.is_(None)))
            stmt = stmt.order_by(Farmer.updated_at.asc(), Farmer.id.asc()).offset(offset).limit(limit + 1)
            rows = list((await self.session.scalars(stmt)).all())
            has_more = len(rows) > limit
            rows = rows[:limit]

            for f in rows:
                del_ms = dt_to_ms(f.deleted_at)
                upd_ms = dt_to_ms(f.updated_at)
                cre_ms = dt_to_ms(f.created_at)

                if del_ms is not None:
                    if last_pulled_at is not None and del_ms > last_pulled_at:
                        deleted.append(f.farmer_id)
                elif last_pulled_at is None or (cre_ms is not None and cre_ms > last_pulled_at):
                    created.append(self._serialize_farmer(f))
                elif upd_ms is not None and upd_ms > last_pulled_at:
                    updated.append(self._serialize_farmer(f))

        elif table == "land_parcels":
            stmt = select(LandParcel).order_by(LandParcel.updated_at.asc(), LandParcel.id.asc()).offset(offset).limit(limit + 1)
            rows = list((await self.session.scalars(stmt)).all())
            has_more = len(rows) > limit
            rows = rows[:limit]

            for p in rows:
                del_ms = dt_to_ms(p.deleted_at)
                upd_ms = dt_to_ms(p.updated_at)
                cre_ms = dt_to_ms(p.created_at)

                if del_ms is not None:
                    if last_pulled_at is not None and del_ms > last_pulled_at:
                        deleted.append(p.farm_id)
                elif last_pulled_at is None or (cre_ms is not None and cre_ms > last_pulled_at):
                    created.append(self._serialize_land_parcel(p))
                elif upd_ms is not None and upd_ms > last_pulled_at:
                    updated.append(self._serialize_land_parcel(p))

        elif table in ("lots", "inventory_lots"):
            stmt = select(Lot).options(selectinload(Lot.assay))
            if org_id:
                stmt = stmt.where(or_(Lot.org_id == org_id, Lot.org_id.is_(None)))
            stmt = stmt.order_by(Lot.updated_at.asc(), Lot.id.asc()).offset(offset).limit(limit + 1)
            rows = list((await self.session.scalars(stmt)).all())
            has_more = len(rows) > limit
            rows = rows[:limit]

            for l in rows:
                del_ms = dt_to_ms(l.deleted_at)
                upd_ms = dt_to_ms(l.updated_at)
                cre_ms = dt_to_ms(l.created_at)

                if del_ms is not None:
                    if last_pulled_at is not None and del_ms > last_pulled_at:
                        deleted.append(l.lot_code)
                elif last_pulled_at is None or (cre_ms is not None and cre_ms > last_pulled_at):
                    created.append(self._serialize_lot(l) if table == "lots" else self._serialize_inventory_lot(l))
                elif upd_ms is not None and upd_ms > last_pulled_at:
                    updated.append(self._serialize_lot(l) if table == "lots" else self._serialize_inventory_lot(l))

        elif table == "assay_reports":
            stmt = select(AssayReport).options(selectinload(AssayReport.lot)).order_by(AssayReport.updated_at.asc(), AssayReport.id.asc()).offset(offset).limit(limit + 1)
            rows = list((await self.session.scalars(stmt)).all())
            has_more = len(rows) > limit
            rows = rows[:limit]

            for a in rows:
                report_id = f"ASSAY-{a.lot.lot_code}" if a.lot else str(a.id)
                del_ms = dt_to_ms(a.deleted_at)
                upd_ms = dt_to_ms(a.updated_at)
                cre_ms = dt_to_ms(a.created_at)

                if del_ms is not None:
                    if last_pulled_at is not None and del_ms > last_pulled_at:
                        deleted.append(report_id)
                elif last_pulled_at is None or (cre_ms is not None and cre_ms > last_pulled_at):
                    created.append(self._serialize_assay(a))
                elif upd_ms is not None and upd_ms > last_pulled_at:
                    updated.append(self._serialize_assay(a))

        elif table == "buyer_demand":
            stmt = select(BuyerDemand)
            if org_id:
                stmt = stmt.where(or_(BuyerDemand.org_id == org_id, BuyerDemand.org_id.is_(None)))
            stmt = stmt.order_by(BuyerDemand.updated_at.asc(), BuyerDemand.id.asc()).offset(offset).limit(limit + 1)
            rows = list((await self.session.scalars(stmt)).all())
            has_more = len(rows) > limit
            rows = rows[:limit]

            for d in rows:
                del_ms = dt_to_ms(d.deleted_at)
                upd_ms = dt_to_ms(d.updated_at)
                cre_ms = dt_to_ms(d.created_at)

                if del_ms is not None:
                    if last_pulled_at is not None and del_ms > last_pulled_at:
                        deleted.append(d.demand_id)
                elif last_pulled_at is None or (cre_ms is not None and cre_ms > last_pulled_at):
                    created.append(self._serialize_demand(d))
                elif upd_ms is not None and upd_ms > last_pulled_at:
                    updated.append(self._serialize_demand(d))

        elif table == "facilities":
            stmt = select(Facility).order_by(Facility.updated_at.asc(), Facility.id.asc()).offset(offset).limit(limit + 1)
            rows = list((await self.session.scalars(stmt)).all())
            has_more = len(rows) > limit
            rows = rows[:limit]

            for fac in rows:
                fac_id = str(fac.id)
                del_ms = dt_to_ms(fac.deleted_at)
                upd_ms = dt_to_ms(fac.updated_at)
                cre_ms = dt_to_ms(fac.created_at)

                if del_ms is not None:
                    if last_pulled_at is not None and del_ms > last_pulled_at:
                        deleted.append(fac_id)
                elif last_pulled_at is None or (cre_ms is not None and cre_ms > last_pulled_at):
                    created.append(self._serialize_facility(fac))
                elif upd_ms is not None and upd_ms > last_pulled_at:
                    updated.append(self._serialize_facility(fac))

        elif table == "market_prices":
            # Snapshot of recent price observations
            stmt = (
                select(
                    PriceObservation,
                    Market.market_name,
                    Market.state_name,
                    Commodity.name,
                )
                .outerjoin(Market, PriceObservation.market_id == Market.id)
                .outerjoin(Commodity, PriceObservation.commodity_id == Commodity.id)
                .order_by(PriceObservation.arrival_date.desc())
                .offset(offset)
                .limit(limit + 1)
            )
            res = list((await self.session.execute(stmt)).all())
            has_more = len(res) > limit
            rows = res[:limit]

            for p, market_name, state_name, commodity_name in rows:
                p_id = f"PRC-{p.market_id}-{p.commodity_id}-{p.arrival_date.isoformat()}"
                created.append({
                    "id": p_id,
                    "commodity": commodity_name or "Commodity",
                    "market_name": market_name or "Market",
                    "state": state_name or "State",
                    "modal_price_inr": float(p.modal_price_inr_per_quintal),
                    "min_price_inr": float(p.min_price_inr_per_quintal),
                    "max_price_inr": float(p.max_price_inr_per_quintal),
                    "observation_date": p.arrival_date.isoformat(),
                    "updated_at": dt_to_ms(datetime.now(UTC)),
                })

        elif table == "trade_contracts":
            stmt = select(TradeContract).order_by(TradeContract.updated_at.asc(), TradeContract.id.asc()).offset(offset).limit(limit + 1)
            rows = list((await self.session.scalars(stmt)).all())
            has_more = len(rows) > limit
            rows = rows[:limit]

            for c in rows:
                del_ms = dt_to_ms(c.deleted_at)
                upd_ms = dt_to_ms(c.updated_at)
                cre_ms = dt_to_ms(c.created_at)

                if del_ms is not None:
                    if last_pulled_at is not None and del_ms > last_pulled_at:
                        deleted.append(c.contract_code)
                elif last_pulled_at is None or (cre_ms is not None and cre_ms > last_pulled_at):
                    created.append(self._serialize_trade_contract(c))
                elif upd_ms is not None and upd_ms > last_pulled_at:
                    updated.append(self._serialize_trade_contract(c))

        elif table == "consent_artifacts":
            stmt = select(ConsentArtifact).order_by(ConsentArtifact.updated_at.asc(), ConsentArtifact.id.asc()).offset(offset).limit(limit + 1)
            rows = list((await self.session.scalars(stmt)).all())
            has_more = len(rows) > limit
            rows = rows[:limit]

            for ca in rows:
                del_ms = dt_to_ms(ca.deleted_at)
                upd_ms = dt_to_ms(ca.updated_at)
                cre_ms = dt_to_ms(ca.created_at)

                if del_ms is not None:
                    if last_pulled_at is not None and del_ms > last_pulled_at:
                        deleted.append(ca.artifact_id)
                elif last_pulled_at is None or (cre_ms is not None and cre_ms > last_pulled_at):
                    created.append(self._serialize_consent(ca))
                elif upd_ms is not None and upd_ms > last_pulled_at:
                    updated.append(self._serialize_consent(ca))
        else:
            has_more = False

        total = len(created) + len(updated) + len(deleted)
        return TableChanges(created=created, updated=updated, deleted=deleted), total, has_more

    # -----------------------------------------------------------------------
    # Serializers
    # -----------------------------------------------------------------------

    def _serialize_farmer(self, f: Farmer) -> dict[str, Any]:
        return {
            "id": f.farmer_id,
            "farmer_id": f.farmer_id,
            "display_name": f.display_name,
            "state_lgd_code": f.state_lgd_code,
            "consent_artifact_id": f.consent_artifact_id,
            "org_id": f.org_id,
            "created_at": dt_to_ms(f.created_at),
            "updated_at": dt_to_ms(f.updated_at),
            "deleted_at": dt_to_ms(f.deleted_at),
        }

    def _serialize_land_parcel(self, p: LandParcel) -> dict[str, Any]:
        return {
            "id": p.farm_id,
            "farmer_id": str(p.farmer_id),
            "farm_id": p.farm_id,
            "area_hectares": float(p.area_hectares) if p.area_hectares else None,
            "created_at": dt_to_ms(p.created_at),
            "updated_at": dt_to_ms(p.updated_at),
            "deleted_at": dt_to_ms(p.deleted_at),
        }

    def _serialize_lot(self, l: Lot) -> dict[str, Any]:
        return {
            "id": l.lot_code,
            "farmer_id": l.farmer_id,
            "commodity": l.commodity,
            "variety": l.variety,
            "quantity_mt": float(l.quantity_mt),
            "status": l.status,
            "consent_artifact_id": l.consent_artifact_id,
            "enam_lot_id": l.enam_lot_id,
            "warehouse_receipt_id": l.warehouse_receipt_id,
            "org_id": l.org_id,
            "created_at": dt_to_ms(l.created_at),
            "updated_at": dt_to_ms(l.updated_at),
            "deleted_at": dt_to_ms(l.deleted_at),
        }

    def _serialize_inventory_lot(self, l: Lot) -> dict[str, Any]:
        return {
            "id": l.lot_code,
            "farmer_id": l.farmer_id,
            "commodity": l.commodity,
            "variety": l.variety,
            "quantity_mt": float(l.quantity_mt),
            "status": l.status,
            "grade": l.assay.grade if l.assay else None,
            "warehouse_id": l.warehouse_id,
            "warehouse_receipt_id": l.warehouse_receipt_id,
            "created_at": dt_to_ms(l.created_at),
            "updated_at": dt_to_ms(l.updated_at),
            "deleted_at": dt_to_ms(l.deleted_at),
        }

    def _serialize_assay(self, a: AssayReport) -> dict[str, Any]:
        report_id = f"ASSAY-{a.lot.lot_code}" if a.lot else str(a.id)
        return {
            "id": report_id,
            "lot_id": a.lot.lot_code if a.lot else str(a.lot_id),
            "grade": a.grade,
            "moisture_percent": float(a.moisture_percent) if a.moisture_percent else None,
            "foreign_matter_percent": float(a.foreign_matter_percent) if a.foreign_matter_percent else None,
            "damaged_percent": float(a.damaged_percent) if a.damaged_percent else None,
            "recorded_at": dt_to_ms(a.recorded_at),
            "created_at": dt_to_ms(a.created_at),
            "updated_at": dt_to_ms(a.updated_at),
            "deleted_at": dt_to_ms(a.deleted_at),
        }

    def _serialize_demand(self, d: BuyerDemand) -> dict[str, Any]:
        return {
            "id": d.demand_id,
            "buyer_id": d.buyer_id,
            "commodity": d.commodity,
            "variety": d.variety,
            "target_grade": d.target_grade,
            "quantity_mt": float(d.quantity_mt),
            "target_price_per_mt": d.target_price_per_mt,
            "delivery_location": d.delivery_location,
            "status": d.status,
            "org_id": d.org_id,
            "created_at": dt_to_ms(d.created_at),
            "updated_at": dt_to_ms(d.updated_at),
            "deleted_at": dt_to_ms(d.deleted_at),
        }

    def _serialize_facility(self, fac: Facility) -> dict[str, Any]:
        return {
            "id": str(fac.id),
            "name": fac.name,
            "facility_type": fac.facility_type,
            "state": fac.state,
            "district": fac.district,
            "capacity_quintals": float(fac.capacity_quintals),
            "available_quintals": float(fac.available_quintals),
            "cold_storage": fac.cold_storage,
            "daily_charge_inr_per_quintal": float(fac.daily_charge_inr_per_quintal),
            "created_at": dt_to_ms(fac.created_at),
            "updated_at": dt_to_ms(fac.updated_at),
            "deleted_at": dt_to_ms(fac.deleted_at),
        }

    def _serialize_trade_contract(self, c: TradeContract) -> dict[str, Any]:
        return {
            "id": c.contract_code,
            "transaction_id": c.transaction_id,
            "lot_code": c.lot_code,
            "farmer_id": c.farmer_id,
            "buyer_name": c.buyer_name,
            "quantity_mt": float(c.quantity_mt),
            "price_inr": c.price_inr,
            "commission_inr": c.commission_inr,
            "status": c.status,
            "settlement_hold": c.settlement_hold,
            "created_at": dt_to_ms(c.created_at),
            "updated_at": dt_to_ms(c.updated_at),
            "deleted_at": dt_to_ms(c.deleted_at),
        }

    def _serialize_consent(self, ca: ConsentArtifact) -> dict[str, Any]:
        return {
            "id": ca.artifact_id,
            "farmer_id": ca.farmer_id,
            "purpose": ca.purpose,
            "status": ca.status,
            "expires_at": dt_to_ms(ca.expires_at),
            "created_at": dt_to_ms(ca.created_at),
            "updated_at": dt_to_ms(ca.updated_at),
            "deleted_at": dt_to_ms(ca.deleted_at),
        }

    # -----------------------------------------------------------------------
    # Push Operation & Conflict Resolution
    # -----------------------------------------------------------------------

    async def push(
        self,
        user_ctx: UserContext,
        payload: SyncPushPayload,
    ) -> SyncPushResponse:
        """Apply pushed changes from offline client, resolving conflicts deterministically."""
        accepted: dict[str, dict[str, int]] = {}
        conflicts: list[ConflictItem] = []
        now = datetime.now(UTC)

        for table, changes in payload.changes.items():
            accepted[table] = {"created": 0, "updated": 0, "deleted": 0}

            # 1. Hard Rule: Server-Authoritative Read-Only Tables
            if table in READ_ONLY_TABLES:
                for item in changes.created + changes.updated:
                    item_id = str(item.get("id", ""))
                    conflicts.append(
                        ConflictItem(
                            table=table,
                            id=item_id,
                            type="read_only_table",
                            resolution="server_authoritative",
                            client_version=item,
                            message=f"Table '{table}' is server-authoritative. Offline modifications are rejected.",
                        )
                    )
                for item_id in changes.deleted:
                    conflicts.append(
                        ConflictItem(
                            table=table,
                            id=str(item_id),
                            type="read_only_table",
                            resolution="server_authoritative",
                            message=f"Table '{table}' is server-authoritative. Offline deletions are rejected.",
                        )
                    )
                continue

            # 2. Process CREATED
            for item in changes.created:
                item_id = str(item.get("id", "")).strip()
                if not item_id:
                    continue

                existing = await self._find_record_by_id(table, item_id)
                if existing is not None:
                    # Conflict: Pushed created with UUID already existing server-side -> treat as update
                    server_snapshot = self._serialize_model(table, existing)
                    self._apply_update_to_model(table, existing, item, now)
                    accepted[table]["updated"] += 1

                    conflicts.append(
                        ConflictItem(
                            table=table,
                            id=item_id,
                            type="created_existing_uuid",
                            resolution="merged_as_update",
                            server_version=server_snapshot,
                            client_version=item,
                            message="Record with this ID already exists on server; merged changes as an update.",
                        )
                    )
                else:
                    # New insert
                    await self._insert_record(table, item, user_ctx, now)
                    accepted[table]["created"] += 1

            # 3. Process UPDATED
            for item in changes.updated:
                item_id = str(item.get("id", "")).strip()
                if not item_id:
                    continue

                existing = await self._find_record_by_id(table, item_id)
                if existing is None:
                    # Record doesn't exist yet -> insert it
                    await self._insert_record(table, item, user_ctx, now)
                    accepted[table]["created"] += 1
                else:
                    server_snapshot = self._serialize_model(table, existing)
                    server_updated_ms = dt_to_ms(getattr(existing, "updated_at", None))
                    client_updated_ms = item.get("updated_at", payload.lastPulledAt)

                    # Check concurrent update conflict
                    if server_updated_ms and client_updated_ms and server_updated_ms > client_updated_ms:
                        # Conflict resolution: Last-writer-wins by (updated_at, actor_id)
                        # Precedence: Server is newer, server wins unless explicit client actor override
                        conflicts.append(
                            ConflictItem(
                                table=table,
                                id=item_id,
                                type="concurrent_update",
                                resolution="server_won",
                                server_version=server_snapshot,
                                client_version=item,
                                message="Concurrent update detected. Server record has newer timestamp; server version retained.",
                            )
                        )
                    else:
                        # Client wins / normal update
                        self._apply_update_to_model(table, existing, item, now)
                        accepted[table]["updated"] += 1

            # 4. Process DELETED
            for item_id_raw in changes.deleted:
                item_id = str(item_id_raw).strip()
                if not item_id:
                    continue

                existing = await self._find_record_by_id(table, item_id)
                if existing is None:
                    continue

                # Hard Rule: Never delete a record that has an active ONDC listing or active pledge lien
                if table in ("lots", "inventory_lots"):
                    lot_code = getattr(existing, "lot_code", item_id)

                    # Check active pledge lien
                    lien_stmt = select(PledgeLoan).where(
                        PledgeLoan.lot_code == lot_code,
                        PledgeLoan.lien_status == "LIEN_MARKED",
                    )
                    active_lien = (await self.session.scalars(lien_stmt)).first()
                    if active_lien is not None:
                        conflicts.append(
                            ConflictItem(
                                table=table,
                                id=item_id,
                                type="delete_rejected",
                                resolution="rejected_active_lien_or_listing",
                                server_version=self._serialize_model(table, existing),
                                message="Cannot delete lot with active pledge lien.",
                            )
                        )
                        continue

                    # Check active ONDC listing or contract
                    if getattr(existing, "status", "") in ("registered", "warehoused", "traded") or getattr(existing, "enam_lot_id", None):
                        conflicts.append(
                            ConflictItem(
                                table=table,
                                id=item_id,
                                type="delete_rejected",
                                resolution="rejected_active_lien_or_listing",
                                server_version=self._serialize_model(table, existing),
                                message="Cannot delete lot with active e-NAM or ONDC registered listing.",
                            )
                        )
                        continue

                # Soft delete with tombstone
                existing.deleted_at = now
                existing.updated_at = now
                accepted[table]["deleted"] += 1

        await self.session.commit()

        for c in conflicts:
            try:
                from app.telemetry.metrics import track_sync_conflict
                track_sync_conflict(table=c.table)
            except Exception:
                pass

        return SyncPushResponse(accepted=accepted, conflicts=conflicts)

    async def _find_record_by_id(self, table: str, item_id: str) -> Any | None:
        if table == "farmers":
            stmt = select(Farmer).where(Farmer.farmer_id == item_id)
            return (await self.session.scalars(stmt)).first()
        elif table == "land_parcels":
            stmt = select(LandParcel).where(LandParcel.farm_id == item_id)
            return (await self.session.scalars(stmt)).first()
        elif table in ("lots", "inventory_lots"):
            stmt = select(Lot).options(selectinload(Lot.assay)).where(Lot.lot_code == item_id)
            return (await self.session.scalars(stmt)).first()
        elif table == "assay_reports":
            lot_code = item_id.replace("ASSAY-", "") if item_id.startswith("ASSAY-") else item_id
            stmt = select(AssayReport).options(selectinload(AssayReport.lot)).join(Lot).where(Lot.lot_code == lot_code)
            res = (await self.session.scalars(stmt)).first()
            if not res and item_id.isdigit():
                stmt2 = select(AssayReport).where(AssayReport.id == int(item_id))
                res = (await self.session.scalars(stmt2)).first()
            return res
        elif table == "buyer_demand":
            stmt = select(BuyerDemand).where(BuyerDemand.demand_id == item_id)
            return (await self.session.scalars(stmt)).first()
        elif table == "facilities":
            if item_id.isdigit():
                stmt = select(Facility).where(Facility.id == int(item_id))
                return (await self.session.scalars(stmt)).first()
            return None
        return None

    async def _insert_record(self, table: str, item: dict[str, Any], user_ctx: UserContext, now: datetime) -> None:
        item_id = str(item.get("id", "")).strip()
        org_id = user_ctx.org_id

        if table == "farmers":
            farmer = Farmer(
                farmer_id=item_id,
                display_name=str(item.get("display_name", "Farmer")),
                state_lgd_code=str(item.get("state_lgd_code", "29")),
                consent_artifact_id=str(item.get("consent_artifact_id", "default-consent")),
                org_id=org_id or item.get("org_id"),
                created_at=now,
                updated_at=now,
            )
            self.session.add(farmer)

        elif table == "land_parcels":
            farmer_id_str = str(item.get("farmer_id", "1"))
            farmer_db_id = int(farmer_id_str) if farmer_id_str.isdigit() else 1
            parcel = LandParcel(
                farmer_id=farmer_db_id,
                farm_id=item_id,
                area_hectares=Decimal(str(item.get("area_hectares", "1.0"))) if item.get("area_hectares") else None,
                created_at=now,
                updated_at=now,
            )
            self.session.add(parcel)

        elif table in ("lots", "inventory_lots"):
            lot = Lot(
                lot_code=item_id if item_id.startswith("LOT-") else f"LOT-{item_id}",
                farmer_id=str(item.get("farmer_id", "FARMER-1")),
                commodity=str(item.get("commodity", "Wheat")),
                variety=str(item.get("variety", "Sharbati")),
                quantity_mt=Decimal(str(item.get("quantity_mt", "10.0"))),
                consent_artifact_id=str(item.get("consent_artifact_id", "default-consent")),
                status=str(item.get("status", "assayed")),
                org_id=org_id or item.get("org_id"),
                enam_lot_id=item.get("enam_lot_id"),
                warehouse_receipt_id=item.get("warehouse_receipt_id"),
                created_at=now,
                updated_at=now,
            )
            grade = str(item.get("grade", "FAQ"))
            lot.assay = AssayReport(
                grade=grade,
                recorded_at=now,
                created_at=now,
                updated_at=now,
            )
            self.session.add(lot)

        elif table == "buyer_demand":
            demand = BuyerDemand(
                demand_id=item_id if item_id.startswith("DEM-") else f"DEM-{item_id}",
                buyer_id=str(item.get("buyer_id", user_ctx.client_id or "buyer-1")),
                org_id=org_id or item.get("org_id"),
                commodity=str(item.get("commodity", "Wheat")),
                variety=item.get("variety"),
                target_grade=item.get("target_grade"),
                quantity_mt=Decimal(str(item.get("quantity_mt", "10.0"))),
                target_price_per_mt=int(item["target_price_per_mt"]) if item.get("target_price_per_mt") else None,
                delivery_location=item.get("delivery_location"),
                status=str(item.get("status", "ACTIVE")),
                created_at=now,
                updated_at=now,
            )
            self.session.add(demand)

    def _apply_update_to_model(self, table: str, model: Any, item: dict[str, Any], now: datetime) -> None:
        if table == "farmers":
            if "display_name" in item:
                model.display_name = str(item["display_name"])
            if "state_lgd_code" in item:
                model.state_lgd_code = str(item["state_lgd_code"])
            if "consent_artifact_id" in item:
                model.consent_artifact_id = str(item["consent_artifact_id"])
        elif table == "land_parcels":
            if "area_hectares" in item and item["area_hectares"] is not None:
                model.area_hectares = Decimal(str(item["area_hectares"]))
        elif table in ("lots", "inventory_lots"):
            if "quantity_mt" in item:
                model.quantity_mt = Decimal(str(item["quantity_mt"]))
            if "variety" in item:
                model.variety = str(item["variety"])
            if "commodity" in item:
                model.commodity = str(item["commodity"])
            if "status" in item:
                model.status = str(item["status"])
            if "warehouse_receipt_id" in item:
                model.warehouse_receipt_id = item["warehouse_receipt_id"]
        elif table == "buyer_demand":
            if "quantity_mt" in item:
                model.quantity_mt = Decimal(str(item["quantity_mt"]))
            if "target_price_per_mt" in item and item["target_price_per_mt"] is not None:
                model.target_price_per_mt = int(item["target_price_per_mt"])
            if "status" in item:
                model.status = str(item["status"])
            if "delivery_location" in item:
                model.delivery_location = item["delivery_location"]

        model.updated_at = now

    def _serialize_model(self, table: str, model: Any) -> dict[str, Any]:
        if table == "farmers":
            return self._serialize_farmer(model)
        elif table == "land_parcels":
            return self._serialize_land_parcel(model)
        elif table == "lots":
            return self._serialize_lot(model)
        elif table == "inventory_lots":
            return self._serialize_inventory_lot(model)
        elif table == "assay_reports":
            return self._serialize_assay(model)
        elif table == "buyer_demand":
            return self._serialize_demand(model)
        elif table == "facilities":
            return self._serialize_facility(model)
        elif table == "trade_contracts":
            return self._serialize_trade_contract(model)
        elif table == "consent_artifacts":
            return self._serialize_consent(model)
        return {}
