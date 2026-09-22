from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.ondc.callback import CallbackError
from app.ondc.quote import build_quote, selected_quantity
from app.ondc.select import SelectService


def test_quote_converts_metric_tons_to_quintals() -> None:
    quote = build_quote(Decimal("12.5"), 2000)

    assert quote["price"] == {"currency": "INR", "value": "250000"}
    assert quote["breakup"][1]["title"] == "delivery"
    assert quote["breakup"][1]["price"]["value"] == "0"


def test_selected_quantity_rejects_more_than_the_lot() -> None:
    assert selected_quantity({"quantity": {"measure": {"value": "3"}}}, Decimal("2")) == "quantity is not available"
    assert selected_quantity({}, Decimal("2")) == Decimal("2")


def _context() -> dict:
    return {
        "domain": "ONDC:AGR10",
        "action": "select",
        "version": "2.0.0",
        "bap_id": "buyer.example",
        "bap_uri": "https://buyer.example/beckn",
        "transaction_id": "txn-9",
        "message_id": "msg-9",
        "timestamp": "2026-09-22T00:00:00Z",
    }


def _lot():
    lot = type("Lot", (), {})()
    lot.lot_code = "LOT-1"
    lot.farmer_id = "MH-400004"
    lot.commodity = "Onion"
    lot.quantity_mt = Decimal("12.5")
    lot.enam_lot_id = "ENAM-9"
    lot.consent_artifact_id = "artifact-lot"
    lot.assay = type("Assay", (), {"grade": "FAQ"})()
    return lot


class _Lots:
    def __init__(self, lot) -> None:
        self.lot = lot

    async def get(self, lot_code: str):
        if self.lot is not None and self.lot.lot_code == lot_code:
            return self.lot
        return None


class _Farmers:
    async def get(self, farmer_id: str):
        return type("Farmer", (), {"farmer_id": farmer_id, "consent_artifact_id": "artifact-lot"})()


class _Consents:
    async def get(self, artifact_id: str):
        now = datetime.now(UTC)
        return type(
            "Artifact",
            (),
            {
                "artifact_id": artifact_id,
                "farmer_id": "MH-400004",
                "purpose": "Market Linkage and Profile Verification",
                "attributes": ["land", "profile"],
                "created_at": now,
                "expires_at": now + timedelta(days=2),
                "status": "active",
            },
        )()


class _Prices:
    def __init__(self, series: list[tuple[date, int]]) -> None:
        self.series = series
        self.commodities: list[str | None] = []

    async def daily_modal_prices(self, query) -> list[tuple[date, int]]:
        self.commodities.append(query.commodity)
        return self.series


class _Callback:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def send(self, bap_uri: str, action: str, payload: dict) -> None:
        self.sent.append((action, payload))


def _service(callback: _Callback, prices: _Prices, lot=_lot()) -> SelectService:
    return SelectService( _Lots(lot), _Farmers(), _Consents(), prices, callback, bpp_id="market.local", bpp_uri="http://market.local/beckn")


async def test_select_quotes_the_latest_modal_price() -> None:
    callback = _Callback()
    prices = _Prices([(date(2026, 9, 20), 1800), (date(2026, 9, 21), 2000)])
    service = _service(callback, prices)

    response = await service.select(
        {
            "context": _context(),
            "message": {
                "order": {
                    "provider": {"id": "MH-400004"},
                    "items": [{"id": "LOT-1", "quantity": {"measure": {"unit": "metric_ton", "value": "2"}}}],
                }
            },
        }
    )

    assert response.status_code == 200
    action, payload = callback.sent[0]
    assert action == "on_select"
    assert payload["context"]["transaction_id"] == "txn-9"
    assert payload["message"]["order"]["quote"]["price"]["value"] == "40000"
    assert prices.commodities == ["Onion"]


async def test_select_nacks_an_unknown_item() -> None:
    callback = _Callback()
    service = _service(callback, _Prices([]), lot=None)

    response = await service.select(
        {"context": _context(), "message": {"order": {"items": [{"id": "LOT-MISSING"}]}}}
    )

    assert response.status_code == 400
    assert callback.sent == []


async def test_select_nacks_when_no_modal_price_exists() -> None:
    service = _service(_Callback(), _Prices([]))

    response = await service.select(
        {"context": _context(), "message": {"order": {"items": [{"id": "LOT-1"}]}}}
    )

    assert response.status_code == 400


def test_select_route_nacks_a_search_action() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )
    context = _context()
    context["action"] = "search"
    with TestClient(application) as client:
        response = client.post("/beckn/select", json={"context": context, "message": {}})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "action must be select"
