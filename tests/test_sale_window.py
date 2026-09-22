from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.prices import get_price_reader
from app.config import Settings
from app.db.session import Database
from app.main import create_app
from app.prices.models import Commodity, Market, PriceObservation
from app.prices.repository import PriceRepository, daily_modal_statement
from app.prices.sale_window import recommend_sale_window
from app.prices.schemas import PriceFilter


def test_rising_prices_recommend_storage_when_the_gain_exceeds_cost() -> None:
    start = date(2026, 9, 1)
    series = [(start, 100), (start + timedelta(days=1), 110), (start + timedelta(days=2), 120)]

    window = recommend_sale_window(series, horizon_days=14, storage_cost_per_quintal_per_day=0)

    assert window.recommendation == "store"
    assert window.projected_modal_price_inr_per_quintal == 260
    assert window.latest_modal_price_inr_per_quintal == 120
    assert window.storage_cost_inr_per_quintal == 0


def test_storage_is_not_recommended_when_the_gain_does_not_cover_cost() -> None:
    start = date(2026, 9, 1)
    series = [(start, 100), (start + timedelta(days=1), 110), (start + timedelta(days=2), 120)]

    window = recommend_sale_window(series, horizon_days=14, storage_cost_per_quintal_per_day=20)

    assert window.recommendation == "sell"
    assert window.storage_cost_inr_per_quintal == 280
    assert "does not cover" in window.reason


def test_one_price_recommends_an_immediate_sale() -> None:
    window = recommend_sale_window(
        [(date(2026, 9, 21), 500)],
        horizon_days=7,
        storage_cost_per_quintal_per_day=0,
    )

    assert window.observations == 1
    assert window.recommendation == "sell"
    assert window.projected_modal_price_inr_per_quintal == 500


def test_daily_modal_statement_groups_by_arrival_date() -> None:
    statement = daily_modal_statement(PriceFilter(commodity="Onion", state="Maharashtra"))
    compiled = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

    assert "GROUP BY" in compiled
    assert "Onion" in compiled
    assert "Maharashtra" in compiled


class _Reader:
    def __init__(self, series: list[tuple[date, int]]) -> None:
        self.series = series
        self.queries: list[PriceFilter] = []

    async def daily_modal_prices(self, query: PriceFilter) -> list[tuple[date, int]]:
        self.queries.append(query)
        return self.series


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


def test_sale_window_route_returns_the_recommendation() -> None:
    start = date(2026, 9, 1)
    reader = _Reader([(start, 100), (start + timedelta(days=1), 110), (start + timedelta(days=2), 120)])

    with _client(reader) as client:
        response = client.get(
            "/api/v1/prices/sale-window",
            params={"commodity": " Onion ", "state": "Maharashtra", "horizon_days": 14},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["commodity"] == "Onion"
    assert body["state"] == "Maharashtra"
    assert body["recommendation"] == "store"
    assert body["projected_modal_price_inr_per_quintal"] == 260
    assert reader.queries[0].arrival_from == date.today() - timedelta(days=90)


def test_sale_window_route_reports_missing_prices() -> None:
    with _client(_Reader([])) as client:
        response = client.get("/api/v1/prices/sale-window", params={"commodity": "Onion"})

    assert response.status_code == 404
    assert response.json()["errors"][0]["title"] == "No prices found"


def test_sale_window_rejects_a_horizon_outside_one_to_three_weeks() -> None:
    with _client(_Reader([])) as client:
        response = client.get(
            "/api/v1/prices/sale-window",
            params={"commodity": "Onion", "horizon_days": 6},
        )

    assert response.status_code == 422
    assert response.json()["errors"][0]["source"]["pointer"] == "/query/horizon_days"


async def test_daily_modal_prices_average_markets_on_the_same_day() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.session_factory() as session:
            repository = PriceRepository(session)
            eastern = await repository.upsert_market(
                state_name="Windowland",
                state_lgd_code=None,
                district_name="East",
                market_name="East Gate",
            )
            western = await repository.upsert_market(
                state_name="Windowland",
                state_lgd_code=None,
                district_name="West",
                market_name="West Gate",
            )
            commodity = await repository.upsert_commodity(name="Window Onion", group_name=None)
            await repository.upsert_observation(
                arrival_date=date(2026, 9, 1),
                market_id=eastern,
                commodity_id=commodity,
                variety="",
                grade="FAQ",
                min_price=90,
                max_price=110,
                modal_price=100,
            )
            await repository.upsert_observation(
                arrival_date=date(2026, 9, 1),
                market_id=western,
                commodity_id=commodity,
                variety="",
                grade="FAQ",
                min_price=140,
                max_price=160,
                modal_price=150,
            )
            await repository.upsert_observation(
                arrival_date=date(2026, 9, 2),
                market_id=eastern,
                commodity_id=commodity,
                variety="",
                grade="FAQ",
                min_price=190,
                max_price=210,
                modal_price=200,
            )
            series = await repository.daily_modal_prices(
                PriceFilter(state="Windowland", commodity="Window Onion", arrival_from=date(2026, 9, 1))
            )
            await session.rollback()
    finally:
        await database.dispose()

    assert series == [(date(2026, 9, 1), 125), (date(2026, 9, 2), 200)]
