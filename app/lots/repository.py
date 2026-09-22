from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.lots.models import AssayReport, Lot
from app.lots.schemas import LotCreateRequest


class LotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, lot_code: str) -> Lot | None:
        statement = select(Lot).where(Lot.lot_code == lot_code).options(selectinload(Lot.assay))
        return await self.session.scalar(statement)

    async def list_for_farmer(self, farmer_id: str) -> list[Lot]:
        statement = (
            select(Lot)
            .where(Lot.farmer_id == farmer_id)
            .options(selectinload(Lot.assay))
            .order_by(Lot.created_at.desc(), Lot.lot_code)
        )
        return list(await self.session.scalars(statement))

    async def list_registered(self, commodity: str | None) -> list[Lot]:
        statement = (
            select(Lot)
            .where(Lot.enam_lot_id.is_not(None))
            .options(selectinload(Lot.assay))
            .order_by(Lot.created_at.desc(), Lot.lot_code)
            .limit(50)
        )
        if commodity is not None:
            statement = statement.where(func.lower(Lot.commodity) == commodity.casefold())
        return list(await self.session.scalars(statement))

    async def create(self, request: LotCreateRequest) -> Lot:
        lot = Lot(
            lot_code=f"LOT-{uuid4().hex[:12].upper()}",
            farmer_id=request.farmer_id,
            commodity=request.commodity.strip(),
            variety=request.variety.strip(),
            quantity_mt=request.quantity_mt,
            consent_artifact_id=request.consent_artifact_id,
            status="assayed",
            created_at=datetime.now(UTC),
        )
        lot.assay = AssayReport(
            grade=request.grade.strip(),
            foreign_matter_percent=request.foreign_matter_percent,
            moisture_percent=request.moisture_percent,
            damaged_percent=request.damaged_percent,
            recorded_at=lot.created_at,
        )
        self.session.add(lot)
        await self.session.flush()
        return lot

    async def assign_gate(self, lot: Lot, gate_id: str) -> None:
        lot.enam_gate_id = gate_id
        await self.session.flush()

    async def assign_enam_lot(self, lot: Lot, enam_lot_id: str) -> None:
        lot.enam_lot_id = enam_lot_id
        lot.status = "registered"
        lot.enam_registered_at = datetime.now(UTC)
        await self.session.flush()

    async def assign_receipt(self, lot: Lot, warehouse_id: str, receipt_id: str) -> None:
        lot.warehouse_id = warehouse_id
        lot.warehouse_receipt_id = receipt_id
        lot.status = "warehoused"
        lot.warehoused_at = datetime.now(UTC)
        await self.session.flush()
