from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    SessionDep,
    SettingsDep,
    get_current_user,
    require_org_access,
    require_roles,
)
from app.consent.repository import ConsentRepository
from app.consent.signing import authorize_profile_fetch
from app.errors import AppError
from app.events.repository import EventRepository
from app.farmers.repository import FarmerRepository
from app.lots.enam import EnamClient, EnamError
from app.lots.grading import evaluate_crop_quality
from app.lots.models import Lot
from app.lots.repository import LotRepository
from app.lots.schemas import (
    AssayEvaluationRequest,
    AssayEvaluationResponse,
    AssayResponse,
    AssayUpdateRequest,
    EnamRegistrationRequest,
    LotCreateRequest,
    LotListResponse,
    LotResponse,
    WarehouseReceiptRequest,
)

router = APIRouter(
    prefix="/lots",
    tags=["lots"],
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles("farmer", "fpo_operator", "assayer", "buyer", "bank", "logistics", "admin", "regulator")),
        Depends(require_org_access("fpo_id")),
    ],
)


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
        warehouse_id=lot.warehouse_id,
        warehouse_receipt_id=lot.warehouse_receipt_id,
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
        grade: str | None = None
        if request.grade.strip().upper() in ("AUTO", "ASSAY_AUTO", "ASSAY-AUTO"):
            grading = evaluate_crop_quality(
                commodity=request.commodity,
                foreign_matter_percent=request.foreign_matter_percent,
                moisture_percent=request.moisture_percent,
                damaged_percent=request.damaged_percent,
            )
            grade = grading.grade
        lot = await self.lots.create(request, grade=grade)
        if isinstance(self.lots, LotRepository):
            await EventRepository(self.session).record_event(
                event_type="LotCreated",
                stream_id=f"lot:{lot.lot_code}",
                partition_key=lot.farmer_id,
                payload={
                    "lot_code": lot.lot_code,
                    "farmer_id": lot.farmer_id,
                    "commodity": lot.commodity,
                    "variety": lot.variety,
                    "quantity_mt": str(lot.quantity_mt),
                    "grade": lot.assay.grade if lot.assay else None,
                },
                consent_artifact_id=lot.consent_artifact_id,
            )
        await self.session.commit()
        return lot_response(lot)

    async def reassay(self, lot_code: str, request: AssayUpdateRequest) -> LotResponse:
        lot = await self.lots.get(lot_code)
        if lot is None or lot.assay is None:
            raise AppError(404, "Lot not found")
        await self._require_consent(lot)
        grade = request.grade.strip()
        if grade.upper() in ("AUTO", "ASSAY_AUTO", "ASSAY-AUTO"):
            grading = evaluate_crop_quality(
                commodity=lot.commodity,
                foreign_matter_percent=request.foreign_matter_percent,
                moisture_percent=request.moisture_percent,
                damaged_percent=request.damaged_percent,
                immature_percent=request.immature_percent,
                weevilled_percent=request.weevilled_percent,
            )
            grade = grading.grade
        await self.lots.update_assay(
            lot=lot,
            grade=grade,
            foreign_matter_percent=request.foreign_matter_percent,
            moisture_percent=request.moisture_percent,
            damaged_percent=request.damaged_percent,
        )
        if isinstance(self.lots, LotRepository):
            await EventRepository(self.session).record_event(
                event_type="AssayCompleted",
                stream_id=f"lot:{lot.lot_code}",
                partition_key=lot.farmer_id,
                payload={
                    "lot_code": lot.lot_code,
                    "farmer_id": lot.farmer_id,
                    "commodity": lot.commodity,
                    "grade": grade,
                    "foreign_matter_percent": str(request.foreign_matter_percent),
                    "moisture_percent": str(request.moisture_percent),
                    "damaged_percent": str(request.damaged_percent),
                },
                consent_artifact_id=lot.consent_artifact_id,
            )
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

    async def issue_receipt(self, lot_code: str, warehouse_id: str) -> LotResponse:
        if self.enam is None:
            raise AppError(503, "Market registry is not configured")
        lot = await self.lots.get(lot_code)
        if lot is None or lot.assay is None:
            raise AppError(404, "Lot not found")
        if lot.warehouse_receipt_id:
            return lot_response(lot)
        if not lot.enam_lot_id:
            raise AppError(409, "Lot is not registered")
        await self._require_consent(lot)
        try:
            receipt_id = await self.enam.issue_receipt(
                enam_lot_id=lot.enam_lot_id,
                lot_code=lot.lot_code,
                commodity=lot.commodity,
                quantity_mt=lot.quantity_mt,
                grade=lot.assay.grade,
                warehouse_id=warehouse_id,
            )
        except EnamError as exc:
            raise AppError(502, "Market registry request failed") from exc
        await self.lots.assign_receipt(lot, warehouse_id, receipt_id)
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


@router.post("/assay-evaluate")
async def evaluate_assay(body: AssayEvaluationRequest) -> AssayEvaluationResponse:
    result = evaluate_crop_quality(
        commodity=body.commodity,
        foreign_matter_percent=body.foreign_matter_percent,
        moisture_percent=body.moisture_percent,
        damaged_percent=body.damaged_percent,
        immature_percent=body.immature_percent,
        weevilled_percent=body.weevilled_percent,
    )
    return AssayEvaluationResponse(
        commodity=result.commodity,
        grade=result.grade,
        is_faq=result.is_faq,
        quality_score=result.quality_score,
        defect_breakdown=result.defect_breakdown,
        standard_used=result.standard_used,
    )


@router.get("")
async def list_lots(
    service: LotServiceDep,
    farmer_id: Annotated[str, Query(min_length=6, max_length=64)],
) -> LotListResponse:
    return await service.list_for_farmer(farmer_id.strip())


@router.get("/{lot_code}")
async def read_lot(lot_code: str, service: LotServiceDep) -> LotResponse:
    return await service.read(lot_code)


@router.post(
    "/{lot_code}/reassay",
    dependencies=[Depends(require_roles("assayer", "fpo_operator", "admin"))],
)
async def reassay_lot(
    lot_code: str,
    body: AssayUpdateRequest,
    service: LotServiceDep,
) -> LotResponse:
    return await service.reassay(lot_code, body)


@router.post("/{lot_code}/enam-registration")
async def register_lot(
    lot_code: str,
    body: EnamRegistrationRequest,
    service: LotServiceDep,
) -> LotResponse:
    return await service.register(lot_code, body.mandi.strip())


@router.post("/{lot_code}/warehouse-receipt")
async def issue_warehouse_receipt(
    lot_code: str,
    body: WarehouseReceiptRequest,
    service: LotServiceDep,
) -> LotResponse:
    return await service.issue_receipt(lot_code, body.warehouse_id.strip())

