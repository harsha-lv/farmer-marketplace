from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.config import Settings
from app.db.session import Database
from app.main import create_app
from app.ondc.callback import CallbackError
from app.ondc.confirm import ConfirmService
from app.trades.models import TradeContract
from app.trades.repository import ContractRepository


def _context() -> dict:
    return {
        "domain": "ONDC:AGR10",
        "action": "confirm",
        "version": "2.0.0",
        "bap_id": "buyer.example",
        "bap_uri": "https://buyer.example/beckn",
        "transaction_id": "txn-confirm-1",
        "message_id": "msg-confirm-1",
        "timestamp": "2026-09-23T00:00:00Z",
    }


def _lot(quantity: Decimal = Decimal("12.5")):
    lot = type("Lot", (), {})()
    lot.lot_code = "LOT-1"
    lot.farmer_id = "MH-400004"
    lot.commodity = "Onion"
    lot.quantity_mt = quantity
    lot.status = "registered"
    lot.enam_lot_id = "ENAM-9"
    lot.consent_artifact_id = "artifact-lot"
    lot.assay = type("Assay", (), {"grade": "FAQ"})()
    return lot


class _Lots:
    def __init__(self, lot=None) -> None:
        self.lot = lot or _lot()
        self.deducted = None

    async def get(self, lot_code: str):
        return self.lot if lot_code == "LOT-1" else None

    async def deduct_quantity(self, lot, quantity: Decimal) -> None:
        self.deducted = quantity
        lot.quantity_mt = max(Decimal(0), lot.quantity_mt - quantity)
        if lot.quantity_mt == Decimal(0):
            lot.status = "traded"


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


class _Session:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class _Contracts:
    def __init__(self, contract=None) -> None:
        self.session = _Session()
        self.contract = contract or type(
            "Contract",
            (),
            {
                "id": 1,
                "contract_code": "TLC-txn-confirm-1",
                "transaction_id": "txn-confirm-1",
                "lot_code": "LOT-1",
                "farmer_id": "MH-400004",
                "buyer_name": "Buyer Co",
                "buyer_address": "Mumbai",
                "buyer_phone": None,
                "delivery_gps": "19.0760,72.8777",
                "quantity_mt": Decimal("2"),
                "price_inr": 44000,
                "commission_inr": 4000,
                "status": "draft",
            },
        )()

    async def get_by_transaction(self, transaction_id: str):
        return self.contract if transaction_id == self.contract.transaction_id else None

    async def confirm(self, contract):
        contract.status = "confirmed"
        return contract


class _Callback:
    def __init__(self, fail: bool = False) -> None:
        self.sent = []
        self.fail = fail

    async def send(self, bap_uri: str, action: str, payload: dict) -> None:
        if self.fail:
            raise CallbackError("on_confirm callback failed")
        self.sent.append((action, payload))


async def test_confirm_transitions_draft_contract_and_deducts_lot_quantity() -> None:
    lots = _Lots()
    contracts = _Contracts()
    callback = _Callback()
    service = ConfirmService(
        lots,
        _Farmers(),
        _Consents(),
        contracts,
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.confirm({"context": _context(), "message": {}})

    assert response.status_code == 200
    assert contracts.contract.status == "confirmed"
    assert contracts.session.commits == 1
    assert lots.deducted == Decimal("2")
    assert lots.lot.quantity_mt == Decimal("10.5")

    action, payload = callback.sent[0]
    assert action == "on_confirm"
    order = payload["message"]["order"]
    assert order["id"] == "ORD-txn-confirm-1"
    assert order["state"] == "Accepted"
    assert order["provider"]["id"] == "MH-400004"
    assert order["items"][0]["id"] == "LOT-1"
    assert order["items"][0]["quantity"]["measure"]["value"] == "2"
    assert order["quote"]["price"]["value"] == "44000"
    assert order["payment"]["status"] == "PAID-TO-ESCROW"
    assert order["tags"][0]["list"][0] == {"code": "id", "value": "TLC-txn-confirm-1"}
    assert order["tags"][0]["list"][1] == {"code": "status", "value": "confirmed"}


async def test_confirm_is_idempotent_for_already_confirmed_contract() -> None:
    lots = _Lots()
    contracts = _Contracts()
    contracts.contract.status = "confirmed"
    callback = _Callback()
    service = ConfirmService(
        lots,
        _Farmers(),
        _Consents(),
        contracts,
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.confirm({"context": _context(), "message": {}})

    assert response.status_code == 200
    assert lots.deducted is None  # Does not double deduct
    assert contracts.session.commits == 0
    assert len(callback.sent) == 1
    assert callback.sent[0][1]["message"]["order"]["tags"][0]["list"][1]["value"] == "confirmed"


async def test_confirm_rejects_missing_contract() -> None:
    contracts = _Contracts()
    contracts.contract.transaction_id = "other-txn"
    callback = _Callback()
    service = ConfirmService(
        _Lots(),
        _Farmers(),
        _Consents(),
        contracts,
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.confirm({"context": _context(), "message": {}})

    assert response.status_code == 400
    assert response.body.decode().find("contract not found") != -1
    assert len(callback.sent) == 0


async def test_confirm_rejects_insufficient_lot_quantity() -> None:
    lots = _Lots(_lot(quantity=Decimal("1.0")))  # Contract asks for 2.0
    contracts = _Contracts()
    callback = _Callback()
    service = ConfirmService(
        lots,
        _Farmers(),
        _Consents(),
        contracts,
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.confirm({"context": _context(), "message": {}})

    assert response.status_code == 400
    assert response.body.decode().find("insufficient quantity available") != -1
    assert contracts.contract.status == "draft"


async def test_confirm_handles_callback_error() -> None:
    lots = _Lots()
    contracts = _Contracts()
    callback = _Callback(fail=True)
    service = ConfirmService(
        lots,
        _Farmers(),
        _Consents(),
        contracts,
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.confirm({"context": _context(), "message": {}})

    assert response.status_code == 400
    assert response.body.decode().find("on_confirm callback failed") != -1


def test_confirm_route_rejects_wrong_action() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )
    context = _context()
    context["action"] = "init"
    with TestClient(application) as client:
        response = client.post("/beckn/confirm", json={"context": context, "message": {}})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "action must be confirm"


async def test_database_contract_confirm_persists() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.session_factory() as session:
            repository = ContractRepository(session)
            contract = await repository.save_draft(
                transaction_id="txn-confirm-db",
                lot_code="LOT-1",
                farmer_id="MH-400004",
                buyer_name="Buyer Co",
                buyer_address="Mumbai",
                buyer_phone=None,
                delivery_gps="19.0760,72.8777",
                quantity_mt=Decimal("2"),
                price_inr=44000,
                commission_inr=4000,
            )
            await session.commit()
            assert contract.status == "draft"

            await repository.confirm(contract)
            await session.commit()

            fetched = await repository.get_by_transaction("txn-confirm-db")
            assert fetched is not None
            assert fetched.status == "confirmed"

            await session.execute(delete(TradeContract).where(TradeContract.transaction_id == "txn-confirm-db"))
            await session.commit()
    finally:
        await database.dispose()
