from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.prices.models import Commodity, Market, PriceObservation
from app.prices.schemas import PriceFilter, PriceRecord


class PricePage:
    def __init__(self, records: list[PriceRecord], count: int) -> None:
        self.records = records
        self.count = count


def apply_price_filters(statement, query: PriceFilter):
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
    return statement


def price_statement(query: PriceFilter, *, paginate: bool = True):
    statement = apply_price_filters(
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
        .join(Commodity, PriceObservation.commodity_id == Commodity.id),
        query,
    )
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


def daily_modal_statement(query: PriceFilter):
    statement = apply_price_filters(
        select(
            PriceObservation.arrival_date.label("arrival_date"),
            func.avg(PriceObservation.modal_price_inr_per_quintal).label("modal_price"),
        )
        .join(Market, PriceObservation.market_id == Market.id)
        .join(Commodity, PriceObservation.commodity_id == Commodity.id),
        query,
    )
    return statement.group_by(PriceObservation.arrival_date).order_by(PriceObservation.arrival_date)


class PriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_prices(self, query: PriceFilter) -> PricePage:
        result = await self.session.execute(price_statement(query))
        records = [PriceRecord.model_validate(row) for row in result.mappings()]
        count = await self.session.scalar(count_statement(query))
        return PricePage(records=records, count=int(count or 0))

    async def daily_modal_prices(self, query: PriceFilter) -> list[tuple[date, int]]:
        result = await self.session.execute(daily_modal_statement(query))
        return [(row.arrival_date, int(round(row.modal_price))) for row in result]

    async def upsert_market(
        self,
        *,
        state_name: str,
        state_lgd_code: str | None,
        district_name: str,
        market_name: str,
    ) -> int:
        statement = insert(Market).values(
            state_name=state_name,
            state_lgd_code=state_lgd_code,
            district_name=district_name,
            district_lgd_code=None,
            market_name=market_name,
        )
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            constraint="uq_markets_state_district_market",
            set_={
                "state_lgd_code": func.coalesce(excluded.state_lgd_code, Market.state_lgd_code),
            },
        ).returning(Market.id)
        market_id = await self.session.scalar(statement)
        if market_id is None:
            raise RuntimeError("market upsert did not return an id")
        return int(market_id)

    async def upsert_commodity(self, *, name: str, group_name: str | None) -> int:
        statement = insert(Commodity).values(name=name, group_name=group_name)
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            constraint="uq_commodities_name",
            set_={"group_name": func.coalesce(excluded.group_name, Commodity.group_name)},
        ).returning(Commodity.id)
        commodity_id = await self.session.scalar(statement)
        if commodity_id is None:
            raise RuntimeError("commodity upsert did not return an id")
        return int(commodity_id)

    async def upsert_observation(
        self,
        *,
        arrival_date: date,
        market_id: int,
        commodity_id: int,
        variety: str,
        grade: str,
        min_price: int,
        max_price: int,
        modal_price: int,
    ) -> None:
        statement = insert(PriceObservation).values(
            arrival_date=arrival_date,
            market_id=market_id,
            commodity_id=commodity_id,
            variety=variety,
            grade=grade,
            min_price_inr_per_quintal=min_price,
            max_price_inr_per_quintal=max_price,
            modal_price_inr_per_quintal=modal_price,
        )
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            index_elements=["arrival_date", "market_id", "commodity_id", "variety", "grade"],
            set_={
                "min_price_inr_per_quintal": excluded.min_price_inr_per_quintal,
                "max_price_inr_per_quintal": excluded.max_price_inr_per_quintal,
                "modal_price_inr_per_quintal": excluded.modal_price_inr_per_quintal,
            },
        )
        await self.session.execute(statement)
