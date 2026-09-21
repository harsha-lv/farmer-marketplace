from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep
from app.errors import AppError
from app.prices.repository import PriceRepository
from app.prices.schemas import PageMeta, PriceFilter, PriceListResponse

router = APIRouter(tags=["prices"])


def get_price_reader(session: SessionDep) -> PriceRepository:
    return PriceRepository(session)


PriceReaderDep = Annotated[PriceRepository, Depends(get_price_reader)]


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@router.get("/prices")
async def list_prices(
    reader: PriceReaderDep,
    state: Annotated[str | None, Query(max_length=128)] = None,
    district: Annotated[str | None, Query(max_length=128)] = None,
    market: Annotated[str | None, Query(max_length=128)] = None,
    commodity: Annotated[str | None, Query(max_length=128)] = None,
    commodity_group: Annotated[str | None, Query(max_length=128)] = None,
    variety: Annotated[str | None, Query(max_length=128)] = None,
    grade: Annotated[str | None, Query(max_length=64)] = None,
    arrival_from: date | None = None,
    arrival_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PriceListResponse:
    if arrival_from is not None and arrival_to is not None and arrival_from > arrival_to:
        raise AppError(
            422,
            "Invalid request",
            "arrival_from must be on or before arrival_to",
        )
    query = PriceFilter(
        state=_blank_to_none(state),
        district=_blank_to_none(district),
        market=_blank_to_none(market),
        commodity=_blank_to_none(commodity),
        commodity_group=_blank_to_none(commodity_group),
        variety=_blank_to_none(variety),
        grade=_blank_to_none(grade),
        arrival_from=arrival_from,
        arrival_to=arrival_to,
        limit=limit,
        offset=offset,
    )
    page = await reader.list_prices(query)
    return PriceListResponse(
        data=page.records,
        meta=PageMeta(limit=limit, offset=offset, count=page.count),
    )
