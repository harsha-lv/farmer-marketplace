from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.consent.repository import ConsentRepository
from app.consent.signing import authorize_profile_fetch
from app.errors import AppError
from app.farmers.repository import FarmerRepository
from app.lots.models import Lot
from app.lots.repository import LotRepository
from app.lots.schemas import AssayResponse, LotCreateRequest, LotListResponse, LotResponse

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
    ) -> None:
        self.session = session
        self.farmers = farmers
        self.consents = consents
        self.lots = lots

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

    async def list_for_farmer(self, farmer_id: str) -> LotListResponse:
        lots = await self.lots.list_for_farmer(farmer_id)
        return LotListResponse(data=[lot_response(lot) for lot in lots if lot.assay is not None])


def get_lot_service(session: SessionDep) -> LotService:
    return LotService(
        session,
        FarmerRepository(session),
        ConsentRepository(session),
        LotRepository(session),
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
