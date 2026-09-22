from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep, SettingsDep
from app.consent.repository import ConsentRepository
from app.consent.signing import authorize_profile_fetch
from app.farmers.repository import FarmerRepository
from app.lots.repository import LotRepository
from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.catalog import (
    ack,
    build_catalog,
    context_error,
    grade_matches,
    intent_filters,
    nack,
    response_context,
)

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


SearchDep = Annotated[SearchService, Depends(get_search_service)]


@router.post("/search")
async def search(request: Request, service: SearchDep) -> JSONResponse:
    try:
        body = await request.json()
    except ValueError:
        context = response_context({}, action="search", bpp_id=service.bpp_id, bpp_uri=service.bpp_uri)
        return JSONResponse(status_code=400, content=nack(context, "context is required"))
    return await service.search(body)
