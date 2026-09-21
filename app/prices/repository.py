from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.prices.models import Commodity, Market, PriceObservation
from app.prices.schemas import PriceFilter, PriceRecord


class PricePage:
    def __init__(self, records: list[PriceRecord], count: int) -> None:
        self.records = records
        self.count = count


def price_statement(query: PriceFilter, *, paginate: bool = True):
    statement = (
        select(
            PriceObservation.arrival_date.label("arrival_date"),
            Market.state_name.label("state"),
            Market.state_lgd_code.label("state_lgd_code"),
            Market.district_name.label("district"),
            Market.district_lgd_code.label("district_lgd_code"),
            Market.market_name.label("market"),
            Commodity.name.label("commodity"),
            Commodity.group_name.label("commodity_group"),
            PriceObservation.variety.label("variety"),
            PriceObservation.grade.label("grade"),
            PriceObservation.min_price_inr_per_quintal.label("min_price_inr_per_quintal"),
            PriceObservation.max_price_inr_per_quintal.label("max_price_inr_per_quintal"),
            PriceObservation.modal_price_inr_per_quintal.label("modal_price_inr_per_quintal"),
            PriceObservation.arrivals_quintal.label("arrivals_quintal"),
        )
        .join(Market, PriceObservation.market_id == Market.id)
        .join(Commodity, PriceObservation.commodity_id == Commodity.id)
    )
    if query.state is not None:
        statement = statement.where(Market.state_name == query.state)
    if query.district is not None:
        statement = statement.where(Market.district_name == query.district)
    if query.market is not None:
        statement = statement.where(Market.market_name == query.market)
    if query.commodity is not None:
        statement = statement.where(Commodity.name == query.commodity)
    if query.commodity_group is not None:
        statement = statement.where(Commodity.group_name == query.commodity_group)
    if query.variety is not None:
        statement = statement.where(PriceObservation.variety == query.variety)
    if query.grade is not None:
        statement = statement.where(PriceObservation.grade == query.grade)
    if query.arrival_from is not None:
        statement = statement.where(PriceObservation.arrival_date >= query.arrival_from)
    if query.arrival_to is not None:
        statement = statement.where(PriceObservation.arrival_date <= query.arrival_to)
    statement = statement.order_by(
        PriceObservation.arrival_date.desc(),
        Market.market_name,
        Commodity.name,
        PriceObservation.variety,
        PriceObservation.grade,
    )
    if paginate:
        statement = statement.limit(query.limit).offset(query.offset)
    return statement


def count_statement(query: PriceFilter):
    filtered = price_statement(query, paginate=False).order_by(None)
    return select(func.count()).select_from(filtered.subquery())


class PriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_prices(self, query: PriceFilter) -> PricePage:
        result = await self.session.execute(price_statement(query))
        records = [PriceRecord.model_validate(row) for row in result.mappings()]
        count = await self.session.scalar(count_statement(query))
        return PricePage(records=records, count=int(count or 0))
