from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.config import Settings
from app.db.session import Database
from app.main import create_app
from app.ondc.callback import CallbackError
from app.ondc.contract import delivery_terms, quote_with_commission
from app.ondc.init import InitService
from app.trades.models import TradeContract
from app.trades.repository import ContractRepository


def test_delivery_terms_require_a_gps_point() -> None:
    assert delivery_terms({"billing": {"name": "Buyer", "address": "Mumbai"}}) == "delivery location is required"
    terms = delivery_terms(
        {
            "billing": {"name": " Buyer ", "address": " Mumbai "},
            "fulfillment": {"end": {"location": {"gps": "19.0760,72.8777"}}},
        }
    )
    assert terms["gps"] == "19.0760,72.8777"
    assert terms["name"] == "Buyer"


def test_commission_is_added_to_the_item_price() -> None:
    quote = quote_with_commission(Decimal("2"), 2000, 10)

    assert quote["breakup"][0]["price"]["value"] == "40000"
    assert quote["breakup"][2]["price"]["value"] == "4000"
    assert quote["price"]["value"] == "44000"


def _context() -> dict:
    return {
        "domain": "ONDC:AGR10",
        "action": "init",
        "version": "2.0.0",
        "bap_id": "buyer.example",
        "bap_uri": "https://buyer.example/beckn",
        "transaction_id": "txn-init",
        "message_id": "msg-init",
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
    async def get(self, lot_code: str):
        return _lot() if lot_code == "LOT-1" else None


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
    async def daily_modal_prices(self, query):
        return [(date(2026, 9, 21), 2000)]


class _Session:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class _Contracts:
    def __init__(self) -> None:
        self.session = _Session()
        self.saved = None

    async def save_draft(self, **kwargs):
        self.saved = kwargs
        return type("Contract", (), {"contract_code": "TLC-txn-init", "status": "draft"})()


class _Callback:
    def __init__(self, fail: bool = False) -> None:
        self.sent = []
        self.fail = fail

    async def send(self, bap_uri: str, action: str, payload: dict) -> None:
        if self.fail:
            raise CallbackError("on_init callback failed")
        self.sent.append((action, payload))


def _message() -> dict:
    return {
        "order": {
            "provider": {"id": "MH-400004"},
            "items": [{"id": "LOT-1", "quantity": {"measure": {"value": "2"}}}],
            "billing": {"name": "Buyer Co", "address": "Mumbai"},
            "fulfillment": {"end": {"location": {"gps": "19.0760,72.8777"}}},
        }
    }


async def test_init_sends_a_draft_contract() -> None:
    contracts = _Contracts()
    callback = _Callback()
    service = InitService(
        _Lots(),
        _Farmers(),
        _Consents(),
        _Prices(),
        contracts,
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
        commission_percent=10,
    )

    response = await service.init({"context": _context(), "message": _message()})

    assert response.status_code == 200
    action, payload = callback.sent[0]
    assert action == "on_init"
    order = payload["message"]["order"]
    assert order["quote"]["price"]["value"] == "44000"
    assert order["payment"]["type"] == "ON-FULFILLMENT"
    assert order["tags"][0]["list"][0] == {"code": "id", "value": "TLC-txn-init"}
    assert contracts.saved["delivery_gps"] == "19.0760,72.8777"
    assert contracts.session.commits == 1


def test_init_route_nacks_a_select_action() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )
    context = _context()
    context["action"] = "select"
    with TestClient(application) as client:
        response = client.post("/beckn/init", json={"context": context, "message": {}})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "action must be init"


async def test_draft_contract_is_replaced_for_the_same_transaction() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.session_factory() as session:
            repository = ContractRepository(session)
            first = await repository.save_draft(
                transaction_id="txn-db",
                lot_code="LOT-1",
                farmer_id="MH-400004",
                buyer_name="Buyer Co",
                buyer_address="Mumbai",
                buyer_phone=None,
                delivery_gps="19.0760,72.8777",
                quantity_mt=Decimal("2"),
                price_inr=40000,
                commission_inr=0,
            )
            second = await repository.save_draft(
                transaction_id="txn-db",
                lot_code="LOT-1",
                farmer_id="MH-400004",
                buyer_name="Buyer Co Updated",
                buyer_address="Pune",
                buyer_phone=None,
                delivery_gps="18.5204,73.8567",
                quantity_mt=Decimal("1"),
                price_inr=20000,
                commission_inr=0,
            )
            await session.commit()
            code = second.contract_code
            name = second.buyer_name
            same_id = first.id == second.id
            await session.execute(delete(TradeContract).where(TradeContract.transaction_id == "txn-db"))
            await session.commit()
    finally:
        await database.dispose()

    assert same_id
    assert code == "TLC-txn-db"
    assert name == "Buyer Co Updated"
