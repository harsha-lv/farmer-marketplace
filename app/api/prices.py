from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, SettingsDep
from app.errors import AppError
from app.prices.feed import FeedError, MandiFeed
from app.prices.ingest import IngestCounts, store_quotes
from app.prices.repository import PriceRepository
from app.prices.sale_window import recommend_sale_window
from app.prices.schemas import IngestResponse, PageMeta, PriceFilter, PriceListResponse, SaleWindowResponse

router = APIRouter(tags=["prices"])


def get_price_reader(session: SessionDep) -> PriceRepository:
    return PriceRepository(session)


PriceReaderDep = Annotated[PriceRepository, Depends(get_price_reader)]


class PriceIngestor:
    def __init__(self, feed: MandiFeed, repository: PriceRepository, session: AsyncSession) -> None:
        self.feed = feed
        self.repository = repository
        self.session = session

    async def run(
        self,
        *,
        state: str | None,
        commodity: str | None,
        max_records: int,
    ) -> IngestCounts:
        records = await self.feed.fetch(state=state, commodity=commodity, max_records=max_records)
        counts = await store_quotes(records, self.repository)
        await self.session.commit()
        return counts


def get_ingestor(session: SessionDep, settings: SettingsDep) -> PriceIngestor:
    if not settings.data_gov_api_key:
        raise AppError(503, "Price source is not configured")
    return PriceIngestor(
        MandiFeed(settings.data_gov_api_key, settings.data_gov_resource_url),
        PriceRepository(session),
        session,
    )


IngestorDep = Annotated[PriceIngestor, Depends(get_ingestor)]


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


@router.post("/prices/ingest")
async def ingest_prices(
    ingestor: IngestorDep,
    state: Annotated[str | None, Query(max_length=128)] = None,
    commodity: Annotated[str | None, Query(max_length=128)] = None,
    max_records: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> IngestResponse:
    try:
        counts = await ingestor.run(
            state=_blank_to_none(state),
            commodity=_blank_to_none(commodity),
            max_records=max_records,
        )
    except FeedError as exc:
        raise AppError(502, "Price source request failed") from exc
    return IngestResponse(fetched=counts.fetched, stored=counts.stored, skipped=counts.skipped)


@router.get("/prices/sale-window")
async def sale_window(
    reader: PriceReaderDep,
    commodity: Annotated[str, Query(min_length=1, max_length=128)],
    state: Annotated[str | None, Query(max_length=128)] = None,
    district: Annotated[str | None, Query(max_length=128)] = None,
    market: Annotated[str | None, Query(max_length=128)] = None,
    variety: Annotated[str | None, Query(max_length=128)] = None,
    grade: Annotated[str | None, Query(max_length=64)] = None,
    horizon_days: Annotated[int, Query(ge=7, le=21)] = 14,
    lookback_days: Annotated[int, Query(ge=7, le=365)] = 90,
    storage_cost_per_quintal_per_day: Annotated[int, Query(ge=0)] = 0,
) -> SaleWindowResponse:
    commodity_name = commodity.strip()
    if not commodity_name:
        raise AppError(422, "Invalid request", "commodity is required")
    query = PriceFilter(
        commodity=commodity_name,
        state=_blank_to_none(state),
        district=_blank_to_none(district),
        market=_blank_to_none(market),
        variety=_blank_to_none(variety),
        grade=_blank_to_none(grade),
        arrival_from=date.today() - timedelta(days=lookback_days),
        limit=1,
    )
    series = await reader.daily_modal_prices(query)
    if not series:
        raise AppError(404, "No prices found")
    window = recommend_sale_window(
        series,
        horizon_days=horizon_days,
        storage_cost_per_quintal_per_day=storage_cost_per_quintal_per_day,
    )
    return SaleWindowResponse(
        commodity=commodity_name,
        state=query.state,
        district=query.district,
        market=query.market,
        horizon_days=horizon_days,
        lookback_days=lookback_days,
        observations=window.observations,
        latest_arrival_date=window.latest_arrival_date,
        latest_modal_price_inr_per_quintal=window.latest_modal_price_inr_per_quintal,
        average_modal_price_inr_per_quintal=window.average_modal_price_inr_per_quintal,
        projected_modal_price_inr_per_quintal=window.projected_modal_price_inr_per_quintal,
        storage_cost_inr_per_quintal=window.storage_cost_inr_per_quintal,
        recommendation=window.recommendation,
        reason=window.reason,
    )
