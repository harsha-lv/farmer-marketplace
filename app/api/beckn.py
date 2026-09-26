import json
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, SettingsDep
from app.consent.repository import ConsentRepository
from app.consent.signing import authorize_profile_fetch
from app.farmers.repository import FarmerRepository
from app.lots.repository import LotRepository
from app.ondc.auth.verification import verify_inbound_beckn_request
from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.cancel import CancelService
from app.ondc.catalog import (
    ack,
    build_catalog,
    context_error,
    grade_matches,
    intent_filters,
    nack,
    response_context,
)
from app.ondc.confirm import ConfirmService
from app.ondc.init import InitService
from app.ondc.rating import RatingService
from app.ondc.schemas import (
    CancelRequest,
    ConfirmRequest,
    InitRequest,
    RatingRequest,
    SearchRequest,
    SelectRequest,
    StatusRequest,
    SupportRequest,
    TrackRequest,
    UpdateRequest,
    build_beckn_nack,
)
from app.ondc.select import SelectService
from app.ondc.shim import (
    apply_deprecation_headers,
    is_v1_request,
    translate_v1_to_v2,
    translate_v2_to_v1,
)
from app.ondc.status import StatusService
from app.ondc.support import SupportService
from app.ondc.track import TrackService
from app.ondc.update import UpdateService
from app.prices.repository import PriceRepository
from app.trades.repository import ContractRepository

router = APIRouter(prefix="/beckn", tags=["beckn"])


class SearchService:
    def __init__(
        self,
        lots: LotRepository,
        farmers: FarmerRepository,
        consents: ConsentRepository,
        callback: BecknCallback,
        *,
        bpp_id: str,
        bpp_uri: str,
        bpp_name: str,
    ) -> None:
        self.lots = lots
        self.farmers = farmers
        self.consents = consents
        self.callback = callback
        self.bpp_id = bpp_id
        self.bpp_uri = bpp_uri
        self.bpp_name = bpp_name

    async def search(self, body: object) -> JSONResponse:
        context = body.get("context") if isinstance(body, dict) else None
        error = context_error(context)
        reply_context = response_context(
            context if isinstance(context, dict) else {},
            action="search",
            bpp_id=self.bpp_id,
            bpp_uri=self.bpp_uri,
        )
        if error is not None or not isinstance(context, dict) or not isinstance(body, dict):
            return JSONResponse(status_code=400, content=nack(reply_context, error or "context is required"))
        commodity, grade = intent_filters(body.get("message"))
        lots = await self._marketable_lots(commodity, grade)
        catalog = build_catalog(lots, self.bpp_name)
        on_search = {
            "context": response_context(context, action="on_search", bpp_id=self.bpp_id, bpp_uri=self.bpp_uri),
            "message": {"catalog": catalog},
        }
        try:
            await self.callback.on_search(str(context["bap_uri"]), on_search)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_search callback failed"))
        return JSONResponse(status_code=200, content=ack(reply_context))

    async def _marketable_lots(self, commodity: str | None, grade: str | None) -> list:
        now = datetime.now(UTC)
        selected = []
        for lot in await self.lots.list_registered(commodity):
            if lot.assay is None or not grade_matches(lot.assay.grade, grade):
                continue
            farmer = await self.farmers.get(lot.farmer_id)
            artifact = await self.consents.get(lot.consent_artifact_id)
            if farmer is None or farmer.consent_artifact_id != lot.consent_artifact_id:
                continue
            record = None if artifact is None else ConsentRepository.record(artifact)
            if authorize_profile_fetch(record, lot.farmer_id, now) is not None:
                continue
            selected.append(lot)
        return selected


class RatingBecknService:
    def __init__(
        self,
        session: AsyncSession,
        callback: BecknCallback,
        *,
        bpp_id: str,
        bpp_uri: str,
    ) -> None:
        self.session = session
        self.callback = callback
        self.bpp_id = bpp_id
        self.bpp_uri = bpp_uri
        self.rating_service = RatingService(session)

    async def rating(self, body: object) -> JSONResponse:
        context = body.get("context") if isinstance(body, dict) else None
        error = context_error(context, action="rating")
        reply_context = response_context(
            context if isinstance(context, dict) else {},
            action="rating",
            bpp_id=self.bpp_id,
            bpp_uri=self.bpp_uri,
        )
        if error is not None or not isinstance(context, dict) or not isinstance(body, dict):
            return JSONResponse(status_code=400, content=nack(reply_context, error or "context is required"))

        message = body.get("message")
        if not isinstance(message, dict):
            return JSONResponse(status_code=400, content=nack(reply_context, "message is required"))

        target_id = str(message.get("id", "")).strip()
        if not target_id:
            return JSONResponse(status_code=400, content=nack(reply_context, "message.id is required"))

        value = message.get("value")
        try:
            score = int(value)
        except (ValueError, TypeError):
            return JSONResponse(status_code=400, content=nack(reply_context, "value must be an integer between 1 and 5"))

        category = str(message.get("rating_category", "seller"))
        feedback = message.get("feedback")

        await self.rating_service.submit_rating(
            transaction_id=str(context.get("transaction_id", "")),
            target_id=target_id,
            score=score,
            rating_category=category,
            feedback=feedback,
        )
        new_score = await self.rating_service.get_seller_score(target_id)

        on_rating = {
            "context": response_context(context, action="on_rating", bpp_id=self.bpp_id, bpp_uri=self.bpp_uri),
            "message": {
                "id": target_id,
                "seller_score": new_score,
                "feedback_ack": True,
            },
        }
        try:
            await self.callback.send(str(context["bap_uri"]), "on_rating", on_rating)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_rating callback failed"))
        return JSONResponse(status_code=200, content=ack(reply_context))


def get_search_service(session: SessionDep, settings: SettingsDep) -> SearchService:
    return SearchService(
        LotRepository(session),
        FarmerRepository(session),
        ConsentRepository(session),
        BecknCallback(),
        bpp_id=settings.ondc_bpp_id,
        bpp_uri=settings.ondc_bpp_uri,
        bpp_name=settings.ondc_bpp_name,
    )


def get_select_service(session: SessionDep, settings: SettingsDep) -> SelectService:
    return SelectService(
        LotRepository(session),
        FarmerRepository(session),
        ConsentRepository(session),
        PriceRepository(session),
        BecknCallback(),
        bpp_id=settings.ondc_bpp_id,
        bpp_uri=settings.ondc_bpp_uri,
    )


def get_init_service(session: SessionDep, settings: SettingsDep) -> InitService:
    return InitService(
        LotRepository(session),
        FarmerRepository(session),
        ConsentRepository(session),
        PriceRepository(session),
        ContractRepository(session),
        BecknCallback(),
        bpp_id=settings.ondc_bpp_id,
        bpp_uri=settings.ondc_bpp_uri,
        commission_percent=settings.ondc_commission_percent,
    )


def get_confirm_service(session: SessionDep, settings: SettingsDep) -> ConfirmService:
    return ConfirmService(
        LotRepository(session),
        FarmerRepository(session),
        ConsentRepository(session),
        ContractRepository(session),
        BecknCallback(),
        bpp_id=settings.ondc_bpp_id,
        bpp_uri=settings.ondc_bpp_uri,
    )


def get_status_service(session: SessionDep, settings: SettingsDep) -> StatusService:
    return StatusService(
        ContractRepository(session),
        BecknCallback(),
        bpp_id=settings.ondc_bpp_id,
        bpp_uri=settings.ondc_bpp_uri,
    )


def get_cancel_service(session: SessionDep, settings: SettingsDep) -> CancelService:
    return CancelService(
        LotRepository(session),
        ContractRepository(session),
        BecknCallback(),
        bpp_id=settings.ondc_bpp_id,
        bpp_uri=settings.ondc_bpp_uri,
    )


def get_support_service(session: SessionDep, settings: SettingsDep) -> SupportService:
    return SupportService(
        ContractRepository(session),
        BecknCallback(),
        bpp_id=settings.ondc_bpp_id,
        bpp_uri=settings.ondc_bpp_uri,
        support_phone=settings.ondc_support_phone,
        support_email=settings.ondc_support_email,
    )


def get_track_service(session: SessionDep, settings: SettingsDep) -> TrackService:
    return TrackService(
        ContractRepository(session),
        BecknCallback(),
        bpp_id=settings.ondc_bpp_id,
        bpp_uri=settings.ondc_bpp_uri,
        tracking_base_url=settings.ondc_tracking_base_url,
    )


def get_update_service(session: SessionDep, settings: SettingsDep) -> UpdateService:
    return UpdateService(
        ContractRepository(session),
        BecknCallback(),
        bpp_id=settings.ondc_bpp_id,
        bpp_uri=settings.ondc_bpp_uri,
    )


def get_rating_service(session: SessionDep, settings: SettingsDep) -> RatingBecknService:
    return RatingBecknService(
        session,
        BecknCallback(),
        bpp_id=settings.ondc_bpp_id,
        bpp_uri=settings.ondc_bpp_uri,
    )


SearchDep = Annotated[SearchService, Depends(get_search_service)]
SelectDep = Annotated[SelectService, Depends(get_select_service)]
InitDep = Annotated[InitService, Depends(get_init_service)]
ConfirmDep = Annotated[ConfirmService, Depends(get_confirm_service)]
StatusDep = Annotated[StatusService, Depends(get_status_service)]
CancelDep = Annotated[CancelService, Depends(get_cancel_service)]
SupportDep = Annotated[SupportService, Depends(get_support_service)]
TrackDep = Annotated[TrackService, Depends(get_track_service)]
UpdateDep = Annotated[UpdateService, Depends(get_update_service)]
RatingDep = Annotated[RatingBecknService, Depends(get_rating_service)]


async def process_beckn_endpoint(
    request: Request,
    model_cls: type,
    action: str,
    bpp_id: str,
    bpp_uri: str,
    handler: Any,
    auth_enabled: bool = False,
) -> JSONResponse:
    reply_context = response_context({}, action=action, bpp_id=bpp_id, bpp_uri=bpp_uri)
    try:
        body_bytes = await request.body()
        if not body_bytes:
            return JSONResponse(
                status_code=400,
                content=build_beckn_nack(reply_context, "30000", "Empty request body", "body"),
            )
        raw_dict = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content=build_beckn_nack(reply_context, "30000", f"Malformed JSON: {exc}", "body"),
        )

    if not isinstance(raw_dict, dict):
        return JSONResponse(
            status_code=400,
            content=build_beckn_nack(reply_context, "30000", "Request body must be a JSON object", "body"),
        )

    # Backwards-compatible v1.2.0 shim detection
    is_v1 = is_v1_request(raw_dict)
    working_dict = translate_v1_to_v2(raw_dict) if is_v1 else raw_dict

    context_dict = working_dict.get("context")
    if isinstance(context_dict, dict):
        reply_context = response_context(context_dict, action=action, bpp_id=bpp_id, bpp_uri=bpp_uri)

    # Inbound network authentication verification
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_enabled or (auth_header and auth_header.startswith("Signature ")):
        is_valid, reason = await verify_inbound_beckn_request(request, body_bytes, context=context_dict)
        if not is_valid:
            return JSONResponse(
                status_code=401,
                content=build_beckn_nack(
                    reply_context,
                    "20001",
                    reason or "Network authentication failed",
                    "headers.authorization",
                ),
            )

    # Strict Pydantic v2 schema validation
    try:
        model_cls.model_validate(working_dict)
    except ValidationError as val_err:
        first_err = val_err.errors()[0]
        loc = ".".join(str(p) for p in first_err["loc"])
        msg = first_err["msg"]
        return JSONResponse(
            status_code=400,
            content=build_beckn_nack(reply_context, "30000", f"Schema validation error at {loc}: {msg}", loc),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content=build_beckn_nack(reply_context, "30000", f"Validation error: {exc}", "message"),
        )

    # Execute business service
    response = await handler(working_dict)

    # If v1 caller, translate response back and set Deprecation headers
    if is_v1:
        if response.status_code == 200:
            content_data = json.loads(response.body.decode("utf-8"))
            downgraded = translate_v2_to_v1(content_data)
            v1_response = JSONResponse(status_code=response.status_code, content=downgraded)
            return apply_deprecation_headers(v1_response)
        return apply_deprecation_headers(response)

    return response


@router.post("/search")
async def search(request: Request, service: SearchDep, settings: SettingsDep) -> JSONResponse:
    return await process_beckn_endpoint(
        request, SearchRequest, "search", service.bpp_id, service.bpp_uri, service.search, settings.ondc_auth_enabled
    )


@router.post("/select")
async def select(request: Request, service: SelectDep, settings: SettingsDep) -> JSONResponse:
    return await process_beckn_endpoint(
        request, SelectRequest, "select", service.bpp_id, service.bpp_uri, service.select, settings.ondc_auth_enabled
    )


@router.post("/init")
async def init(request: Request, service: InitDep, settings: SettingsDep) -> JSONResponse:
    return await process_beckn_endpoint(
        request, InitRequest, "init", service.bpp_id, service.bpp_uri, service.init, settings.ondc_auth_enabled
    )


@router.post("/confirm")
async def confirm(request: Request, service: ConfirmDep, settings: SettingsDep) -> JSONResponse:
    return await process_beckn_endpoint(
        request, ConfirmRequest, "confirm", service.bpp_id, service.bpp_uri, service.confirm, settings.ondc_auth_enabled
    )


@router.post("/status")
async def status(request: Request, service: StatusDep, settings: SettingsDep) -> JSONResponse:
    return await process_beckn_endpoint(
        request, StatusRequest, "status", service.bpp_id, service.bpp_uri, service.status, settings.ondc_auth_enabled
    )


@router.post("/cancel")
async def cancel(request: Request, service: CancelDep, settings: SettingsDep) -> JSONResponse:
    return await process_beckn_endpoint(
        request, CancelRequest, "cancel", service.bpp_id, service.bpp_uri, service.cancel, settings.ondc_auth_enabled
    )


@router.post("/support")
async def support(request: Request, service: SupportDep, settings: SettingsDep) -> JSONResponse:
    return await process_beckn_endpoint(
        request, SupportRequest, "support", service.bpp_id, service.bpp_uri, service.support, settings.ondc_auth_enabled
    )


@router.post("/track")
async def track(request: Request, service: TrackDep, settings: SettingsDep) -> JSONResponse:
    return await process_beckn_endpoint(
        request, TrackRequest, "track", service.bpp_id, service.bpp_uri, service.track, settings.ondc_auth_enabled
    )


@router.post("/update")
async def update(request: Request, service: UpdateDep, settings: SettingsDep) -> JSONResponse:
    return await process_beckn_endpoint(
        request, UpdateRequest, "update", service.bpp_id, service.bpp_uri, service.update, settings.ondc_auth_enabled
    )


@router.post("/rating")
async def rating(request: Request, service: RatingDep, settings: SettingsDep) -> JSONResponse:
    return await process_beckn_endpoint(
        request, RatingRequest, "rating", service.bpp_id, service.bpp_uri, service.rating, settings.ondc_auth_enabled
    )
