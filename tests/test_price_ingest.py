from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.prices import get_ingestor
from app.config import Settings
from app.db.session import Database
from app.main import create_app
from app.prices.feed import FeedError, MandiFeed, QuoteRejected, parse_quote
from app.prices.ingest import IngestCounts, store_quotes
from app.prices.lgd import state_lgd_code
from app.prices.models import Market
from app.prices.repository import PriceRepository
from app.prices.schemas import PriceFilter


def test_state_codes_follow_the_directory() -> None:
    assert state_lgd_code("Maharashtra") == "27"
    assert state_lgd_code("NCT of Delhi") == "7"
    assert state_lgd_code("Orissa") == "21"
    assert state_lgd_code("Jammu & Kashmir") == "1"
    assert state_lgd_code("Not A State") is None


def test_parse_quote_maps_a_source_row() -> None:
    quote = parse_quote(
        {
            "state": " Maharashtra ",
            "district": "Nashik",
            "market": "Lasalgaon",
            "commodity": "Onion",
            "variety": "Red",
            "grade": "FAQ",
            "arrival_date": "21/09/2026",
            "min_price": "1,200",
            "max_price": "1600",
            "modal_price": "1450",
        }
    )

    assert quote.state == "Maharashtra"
    assert quote.arrival_date == date(2026, 9, 21)
    assert quote.min_price == 1200
    assert quote.state_lgd_code == "27"
    assert quote.variety == "Red"


def test_parse_quote_rejects_a_non_numeric_price() -> None:
    with pytest.raises(QuoteRejected):
        parse_quote(
            {
                "state": "Goa",
                "district": "North Goa",
                "market": "Mapusa",
                "commodity": "Onion",
                "arrival_date": "2026-09-21",
                "min_price": "NR",
                "max_price": "10",
                "modal_price": "10",
            }
        )


class _Sink:
    def __init__(self) -> None:
        self.markets: list[dict] = []
        self.observations: list[tuple] = []

    async def upsert_market(self, **kwargs) -> int:
        self.markets.append(kwargs)
        return 1

    async def upsert_commodity(self, **kwargs) -> int:
        return 2

    async def upsert_observation(self, **kwargs) -> None:
        self.observations.append(kwargs)


async def test_store_quotes_skips_invalid_rows() -> None:
    sink = _Sink()
    counts = await store_quotes(
        [
            {
                "state": "Kerala",
                "district": "Ernakulam",
                "market": "Kochi",
                "commodity": "Banana",
                "arrival_date": "2026-09-01",
                "min_price": "10",
                "max_price": "12",
                "modal_price": "11",
            },
            {"state": "Kerala"},
        ],
        sink,
    )

    assert counts == IngestCounts(fetched=2, stored=1, skipped=1)
    assert sink.markets[0]["state_lgd_code"] == "32"
    assert sink.observations[0]["variety"] == ""
    assert sink.observations[0]["grade"] == ""


def _feed_transport(pages: list[list[dict]]) -> httpx.MockTransport:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api-key"] == "secret-key"
        assert request.url.params["filters[state.keyword]"] == "Maharashtra"
        assert request.url.params["filters[commodity]"] == "Onion"
        page = pages[calls["count"]] if calls["count"] < len(pages) else []
        calls["count"] += 1
        return httpx.Response(200, json={"records": page})

    return httpx.MockTransport(handler)


async def test_feed_pages_until_the_record_cap() -> None:
    feed = MandiFeed(
        "secret-key",
        "https://prices.example/resource",
        transport=_feed_transport([[{"state": "Maharashtra"}] * 100, [{"state": "Maharashtra"}]]),
    )

    records = await feed.fetch(state="Maharashtra", commodity="Onion", max_records=150)

    assert len(records) == 101


async def test_feed_hides_transport_failures() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="api-key=secret-key")

    feed = MandiFeed("secret-key", "https://prices.example/resource", transport=httpx.MockTransport(handler))

    with pytest.raises(FeedError) as caught:
        await feed.fetch(state=None, commodity=None, max_records=10)

    assert "secret-key" not in str(caught.value)


class _Ingestor:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    async def run(self, *, state: str | None, commodity: str | None, max_records: int) -> IngestCounts:
        self.calls.append({"state": state, "commodity": commodity, "max_records": max_records})
        if self.error:
            raise self.error
        return IngestCounts(fetched=2, stored=1, skipped=1)


def _client(settings: Settings, ingestor: _Ingestor | None = None) -> TestClient:
    application = create_app(settings)
    if ingestor is not None:
        application.dependency_overrides[get_ingestor] = lambda: ingestor
    return TestClient(application)


def test_ingest_requires_an_api_key() -> None:
    settings = Settings(
        environment="test",
        log_level="WARNING",
        database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        data_gov_api_key="",
    )

    with _client(settings) as client:
        response = client.post("/api/v1/prices/ingest")

    assert response.status_code == 503
    assert response.json()["errors"][0]["title"] == "Price source is not configured"


def test_ingest_returns_counts_and_hides_source_errors() -> None:
    settings = Settings(
        environment="test",
        log_level="WARNING",
        database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        data_gov_api_key="secret-key",
    )
    ingestor = _Ingestor()

    with _client(settings, ingestor) as client:
        response = client.post(
            "/api/v1/prices/ingest",
            params={"state": " Maharashtra ", "commodity": "Onion", "max_records": 25},
        )

    assert response.status_code == 200
    assert response.json() == {"fetched": 2, "stored": 1, "skipped": 1}
    assert ingestor.calls == [{"state": "Maharashtra", "commodity": "Onion", "max_records": 25}]

    failing = _Ingestor(error=FeedError("price source returned 500 api-key=secret-key"))
    with _client(settings, failing) as client:
        response = client.post("/api/v1/prices/ingest")

    assert response.status_code == 502
    assert "secret-key" not in response.text


async def test_repository_upsert_is_idempotent() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.session_factory() as session:
            repository = PriceRepository(session)
            first_market = await repository.upsert_market(
                state_name="Ingestland",
                state_lgd_code="27",
                district_name="Sample",
                market_name="Gate",
            )
            second_market = await repository.upsert_market(
                state_name="Ingestland",
                state_lgd_code=None,
                district_name="Sample",
                market_name="Gate",
            )
            commodity = await repository.upsert_commodity(name="Ingest Onion", group_name="Vegetables")
            again = await repository.upsert_commodity(name="Ingest Onion", group_name=None)
            await repository.upsert_observation(
                arrival_date=date(2026, 9, 21),
                market_id=first_market,
                commodity_id=commodity,
                variety="",
                grade="FAQ",
                min_price=100,
                max_price=120,
                modal_price=110,
            )
            await repository.upsert_observation(
                arrival_date=date(2026, 9, 21),
                market_id=first_market,
                commodity_id=commodity,
                variety="",
                grade="FAQ",
                min_price=200,
                max_price=220,
                modal_price=210,
            )
            stored = await session.scalar(select(Market).where(Market.state_name == "Ingestland"))
            page = await repository.list_prices(PriceFilter(state="Ingestland", commodity="Ingest Onion"))
            state_code = None if stored is None else stored.state_lgd_code
            modal_price = page.records[0].modal_price_inr_per_quintal
            await session.rollback()
    finally:
        await database.dispose()

    assert first_market == second_market
    assert commodity == again
    assert state_code == "27"
    assert modal_price == 210
