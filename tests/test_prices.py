from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint, text
from sqlalchemy.dialects import postgresql

from app.api.prices import get_price_reader
from app.config import Settings
from app.db.session import Database
from app.main import create_app
from app.prices.models import Commodity, Market, PriceObservation
from app.prices.repository import PriceRepository, count_statement, price_statement
from app.prices.schemas import PriceFilter, PriceRecord


class _Reader:
    def __init__(self, records: list[PriceRecord], count: int) -> None:
        self.records = records
        self.count = count
        self.queries: list[PriceFilter] = []

    async def list_prices(self, query: PriceFilter):
        self.queries.append(query)
        return type("Page", (), {"records": self.records, "count": self.count})()


def _client(reader: _Reader) -> TestClient:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )
    application.dependency_overrides[get_price_reader] = lambda: reader
    return TestClient(application)


def test_price_primary_key_includes_the_time_column() -> None:
    columns = [column.name for column in PriceObservation.__table__.primary_key.columns]
    assert columns[0] == "arrival_date"
    assert "market_id" in columns
    assert "commodity_id" in columns


def test_price_checks_reject_negative_values() -> None:
    names = {
        constraint.name
        for constraint in PriceObservation.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_price_observations_min_price_nonnegative" in names
    assert "ck_price_observations_modal_price_nonnegative" in names
    assert "ck_price_observations_arrivals_nonnegative" in names


def test_statement_filters_state_commodity_and_dates() -> None:
    statement = price_statement(
        PriceFilter(
            state="Maharashtra",
            commodity="Onion",
            arrival_from=date(2026, 9, 1),
            arrival_to=date(2026, 9, 21),
            limit=10,
            offset=20,
        )
    )
    compiled = str(
        statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "Maharashtra" in compiled
    assert "Onion" in compiled
    assert "2026-09-01" in compiled
    assert "2026-09-21" in compiled
    assert "LIMIT 10" in compiled
    assert "OFFSET 20" in compiled

    counted = str(
        count_statement(
            PriceFilter(state="Maharashtra", commodity="Onion")
        ).compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "count" in counted.lower()
    assert "LIMIT" not in counted


def test_list_prices_returns_records_and_page_meta() -> None:
    reader = _Reader(
        records=[
            PriceRecord(
                arrival_date=date(2026, 9, 21),
                state="Maharashtra",
                state_lgd_code="27",
                district="Nashik",
                district_lgd_code=None,
                market="Lasalgaon",
                commodity="Onion",
                commodity_group="Vegetables",
                variety="Red",
                grade="FAQ",
                min_price_inr_per_quintal=1200,
                max_price_inr_per_quintal=1600,
                modal_price_inr_per_quintal=1450,
                arrivals_quintal=Decimal("350.50"),
            )
        ],
        count=1,
    )

    with _client(reader) as client:
        response = client.get(
            "/api/v1/prices",
            params={"state": " Maharashtra ", "commodity": "Onion", "limit": 10},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"limit": 10, "offset": 0, "count": 1}
    assert body["data"][0]["market"] == "Lasalgaon"
    assert body["data"][0]["modal_price_inr_per_quintal"] == 1450
    assert body["data"][0]["arrivals_quintal"] == "350.50"
    assert reader.queries[0].state == "Maharashtra"
    assert reader.queries[0].commodity == "Onion"
    assert reader.queries[0].limit == 10


def test_blank_filters_are_omitted() -> None:
    reader = _Reader(records=[], count=0)

    with _client(reader) as client:
        response = client.get("/api/v1/prices", params={"district": "   "})

    assert response.status_code == 200
    assert reader.queries[0].district is None


def test_reversed_date_range_is_rejected() -> None:
    reader = _Reader(records=[], count=0)

    with _client(reader) as client:
        response = client.get(
            "/api/v1/prices",
            params={"arrival_from": "2026-09-21", "arrival_to": "2026-09-01"},
        )

    assert response.status_code == 422
    assert response.json()["errors"][0]["detail"] == "arrival_from must be on or before arrival_to"
    assert reader.queries == []


def test_limit_above_maximum_is_rejected() -> None:
    reader = _Reader(records=[], count=0)

    with _client(reader) as client:
        response = client.get("/api/v1/prices", params={"limit": 201})

    assert response.status_code == 422
    assert response.json()["errors"][0]["source"]["pointer"] == "/query/limit"
    assert reader.queries == []


async def test_repository_reads_an_inserted_observation() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.engine.connect() as connection:
            table = await connection.scalar(text("SELECT to_regclass('app.price_observations')"))
        if table is None:
            pytest.skip("price migration has not been applied")

        async with database.session_factory() as session:
            market = Market(
                state_name="Testland",
                state_lgd_code="99",
                district_name="Sample",
                district_lgd_code=None,
                market_name="Gate",
            )
            commodity = Commodity(name="Test Onion", group_name="Vegetables")
            session.add_all([market, commodity])
            await session.flush()
            session.add(
                PriceObservation(
                    arrival_date=date(2026, 9, 21),
                    market_id=market.id,
                    commodity_id=commodity.id,
                    variety="Red",
                    grade="FAQ",
                    min_price_inr_per_quintal=1000,
                    max_price_inr_per_quintal=1400,
                    modal_price_inr_per_quintal=1200,
                    arrivals_quintal=Decimal("12.5"),
                )
            )
            await session.flush()

            page = await PriceRepository(session).list_prices(
                PriceFilter(state="Testland", commodity="Test Onion")
            )
            await session.rollback()
    finally:
        await database.dispose()

    assert page.count == 1
    record = page.records[0]
    assert record.market == "Gate"
    assert record.modal_price_inr_per_quintal == 1200
    assert record.arrivals_quintal == Decimal("12.5")
    assert record.state_lgd_code == "99"
