from decimal import Decimal

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.ondc.callback import CallbackError
from app.ondc.cancel import CancelService


def _context() -> dict:
    return {
        "domain": "ONDC:AGR10",
        "action": "cancel",
        "version": "2.0.0",
        "bap_id": "buyer.example",
        "bap_uri": "https://buyer.example/beckn",
        "transaction_id": "txn-cancel-1",
        "message_id": "msg-cancel-1",
        "timestamp": "2026-09-23T00:00:00Z",
    }


def _lot(quantity: Decimal = Decimal("10.5"), status: str = "registered"):
    lot = type("Lot", (), {})()
    lot.lot_code = "LOT-1"
    lot.farmer_id = "MH-400004"
    lot.quantity_mt = quantity
    lot.status = status
    return lot


class _Lots:
    def __init__(self, lot=None) -> None:
        self.lot = lot or _lot()
        self.restored = None

    async def get(self, lot_code: str):
        return self.lot if lot_code == "LOT-1" else None

    async def restore_quantity(self, lot, quantity: Decimal) -> None:
        self.restored = quantity
        lot.quantity_mt += quantity
        if lot.status == "traded":
            lot.status = "registered"


class _Session:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class _Contracts:
    def __init__(self, status: str = "confirmed") -> None:
        self.session = _Session()
        self.contract = type(
            "Contract",
            (),
            {
                "id": 1,
                "contract_code": "TLC-txn-cancel-1",
                "transaction_id": "txn-cancel-1",
                "lot_code": "LOT-1",
                "farmer_id": "MH-400004",
                "buyer_name": "Buyer Co",
                "buyer_address": "Mumbai",
                "quantity_mt": Decimal("2"),
                "status": status,
            },
        )()

    async def get_by_transaction(self, transaction_id: str):
        return self.contract if transaction_id == self.contract.transaction_id else None

    async def cancel(self, contract):
        contract.status = "cancelled"
        return contract


class _Callback:
    def __init__(self, fail: bool = False) -> None:
        self.sent = []
        self.fail = fail

    async def send(self, bap_uri: str, action: str, payload: dict) -> None:
        if self.fail:
            raise CallbackError("on_cancel callback failed")
        self.sent.append((action, payload))


async def test_cancel_confirmed_contract_restores_lot_inventory() -> None:
    lots = _Lots(_lot(quantity=Decimal("10.5"), status="traded"))
    contracts = _Contracts(status="confirmed")
    callback = _Callback()
    service = CancelService(
        lots,
        contracts,
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.cancel(
        {
            "context": _context(),
            "message": {"cancellation_reason_id": "001"},
        }
    )

    assert response.status_code == 200
    assert contracts.contract.status == "cancelled"
    assert contracts.session.commits == 1
    assert lots.restored == Decimal("2")
    assert lots.lot.quantity_mt == Decimal("12.5")
    assert lots.lot.status == "registered"

    action, payload = callback.sent[0]
    assert action == "on_cancel"
    order = payload["message"]["order"]
    assert order["id"] == "ORD-txn-cancel-1"
    assert order["state"] == "Cancelled"
    assert order["tags"][0]["list"][1]["value"] == "cancelled"


async def test_cancel_is_idempotent_for_already_cancelled_contract() -> None:
    lots = _Lots()
    contracts = _Contracts(status="cancelled")
    callback = _Callback()
    service = CancelService(
        lots,
        contracts,
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.cancel({"context": _context(), "message": {}})

    assert response.status_code == 200
    assert lots.restored is None  # Does not re-restore
    assert contracts.session.commits == 0
    assert len(callback.sent) == 1


async def test_cannot_cancel_settled_contract() -> None:
    contracts = _Contracts(status="settled")
    service = CancelService(
        _Lots(),
        contracts,
        _Callback(),
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.cancel({"context": _context(), "message": {}})

    assert response.status_code == 400
    assert response.body.decode().find("cannot cancel settled order") != -1


async def test_cancel_missing_contract() -> None:
    contracts = _Contracts()
    context = _context()
    context["transaction_id"] = "non-existent"
    service = CancelService(
        _Lots(),
        contracts,
        _Callback(),
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.cancel({"context": context, "message": {}})

    assert response.status_code == 400
    assert response.body.decode().find("contract not found") != -1


def test_cancel_route_rejects_wrong_action() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )
    context = _context()
    context["action"] = "status"
    with TestClient(application) as client:
        response = client.post("/beckn/cancel", json={"context": context, "message": {}})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "action must be cancel"
