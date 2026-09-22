from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, SettingsDep
from app.consent.repository import ConsentRepository
from app.consent.signing import authorize_profile_fetch
from app.errors import AppError
from app.farmers.repository import FarmerRepository
from app.lots.enam import EnamClient, EnamError
from app.lots.models import Lot
from app.lots.repository import LotRepository
from app.lots.schemas import (
    AssayResponse,
    EnamRegistrationRequest,
    LotCreateRequest,
    LotListResponse,
    LotResponse,
)

router = APIRouter(prefix="/lots", tags=["lots"])


def lot_response(lot: Lot) -> LotResponse:
    assay = lot.assay
    return LotResponse(
        lot_code=lot.lot_code,
        farmer_id=lot.farmer_id,
        commodity=lot.commodity,
        variety=lot.variety,
        quantity_mt=lot.quantity_mt,
        consent_artifact_id=lot.consent_artifact_id,
        status=lot.status,
        created_at=lot.created_at,
        enam_gate_id=lot.enam_gate_id,
        enam_lot_id=lot.enam_lot_id,
        assay=AssayResponse(
            grade=assay.grade,
            foreign_matter_percent=assay.foreign_matter_percent,
            moisture_percent=assay.moisture_percent,
            damaged_percent=assay.damaged_percent,
            recorded_at=assay.recorded_at,
        ),
    )


class LotService:
    def __init__(
        self,
        session: AsyncSession,
        farmers: FarmerRepository,
        consents: ConsentRepository,
        lots: LotRepository,
        enam: EnamClient | None,
    ) -> None:
        self.session = session
        self.farmers = farmers
        self.consents = consents
        self.lots = lots
        self.enam = enam

    async def create(self, request: LotCreateRequest) -> LotResponse:
        farmer = await self.farmers.get(request.farmer_id)
        if farmer is None:
            raise AppError(404, "Farmer not found")
        artifact = await self.consents.get(request.consent_artifact_id)
        reason = authorize_profile_fetch(
            None if artifact is None else ConsentRepository.record(artifact),
            request.farmer_id,
            datetime.now(UTC),
        )
        if reason is not None:
            raise AppError(403, reason)
        if farmer.consent_artifact_id != request.consent_artifact_id:
            raise AppError(403, "Consent does not match the stored profile")
        lot = await self.lots.create(request)
        await self.session.commit()
        return lot_response(lot)

    async def read(self, lot_code: str) -> LotResponse:
        lot = await self.lots.get(lot_code)
        if lot is None or lot.assay is None:
            raise AppError(404, "Lot not found")
        return lot_response(lot)

    async def register(self, lot_code: str, mandi: str) -> LotResponse:
        if self.enam is None:
            raise AppError(503, "Market registry is not configured")
        lot = await self.lots.get(lot_code)
        if lot is None or lot.assay is None:
            raise AppError(404, "Lot not found")
        if lot.enam_lot_id:
            return lot_response(lot)
        await self._require_consent(lot)
        if not lot.enam_gate_id:
            try:
                gate_id = await self.enam.open_gate(
                    lot_code=lot.lot_code,
                    farmer_id=lot.farmer_id,
                    commodity=lot.commodity,
                    quantity_mt=lot.quantity_mt,
                    grade=lot.assay.grade,
                    mandi=mandi,
                )
            except EnamError as exc:
                raise AppError(502, "Market registry request failed") from exc
            await self.lots.assign_gate(lot, gate_id)
            await self.session.commit()
        try:
            enam_lot_id = await self.enam.create_lot(
                gate_id=lot.enam_gate_id or "",
                lot_code=lot.lot_code,
                commodity=lot.commodity,
                quantity_mt=lot.quantity_mt,
                grade=lot.assay.grade,
                variety=lot.variety,
            )
        except EnamError as exc:
            raise AppError(502, "Market registry request failed") from exc
        await self.lots.assign_enam_lot(lot, enam_lot_id)
        await self.session.commit()
        return lot_response(lot)

    async def _require_consent(self, lot: Lot) -> None:
        farmer = await self.farmers.get(lot.farmer_id)
        if farmer is None:
            raise AppError(404, "Farmer not found")
        artifact = await self.consents.get(lot.consent_artifact_id)
        reason = authorize_profile_fetch(
            None if artifact is None else ConsentRepository.record(artifact),
            lot.farmer_id,
            datetime.now(UTC),
        )
        if reason is not None:
            raise AppError(403, reason)
        if farmer.consent_artifact_id != lot.consent_artifact_id:
            raise AppError(403, "Consent does not match the stored profile")

    async def list_for_farmer(self, farmer_id: str) -> LotListResponse:
        lots = await self.lots.list_for_farmer(farmer_id)
        return LotListResponse(data=[lot_response(lot) for lot in lots if lot.assay is not None])


def get_lot_service(session: SessionDep, settings: SettingsDep) -> LotService:
    enam = EnamClient(settings.enam_base_url) if settings.enam_base_url else None
    return LotService(
        session,
        FarmerRepository(session),
        ConsentRepository(session),
        LotRepository(session),
        enam,
    )


LotServiceDep = Annotated[LotService, Depends(get_lot_service)]


@router.post("")
async def create_lot(body: LotCreateRequest, service: LotServiceDep) -> LotResponse:
    return await service.create(body)


@router.get("")
async def list_lots(
    service: LotServiceDep,
    farmer_id: Annotated[str, Query(min_length=6, max_length=64)],
) -> LotListResponse:
    return await service.list_for_farmer(farmer_id.strip())


@router.get("/{lot_code}")
async def read_lot(lot_code: str, service: LotServiceDep) -> LotResponse:
    return await service.read(lot_code)


@router.post("/{lot_code}/enam-registration")
async def register_lot(
    lot_code: str,
    body: EnamRegistrationRequest,
    service: LotServiceDep,
) -> LotResponse:
    return await service.register(lot_code, body.mandi.strip())
