from decimal import Decimal

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.ondc.callback import CallbackError
from app.ondc.status import StatusService


def _context() -> dict:
    return {
        "domain": "ONDC:AGR10",
        "action": "status",
        "version": "2.0.0",
        "bap_id": "buyer.example",
        "bap_uri": "https://buyer.example/beckn",
        "transaction_id": "txn-status-1",
        "message_id": "msg-status-1",
        "timestamp": "2026-09-23T00:00:00Z",
    }


def _contract(status: str = "confirmed"):
    return type(
        "Contract",
        (),
        {
            "id": 1,
            "contract_code": "TLC-txn-status-1",
            "transaction_id": "txn-status-1",
            "lot_code": "LOT-1",
            "farmer_id": "MH-400004",
            "buyer_name": "Buyer Co",
            "buyer_address": "Mumbai",
            "buyer_phone": None,
            "delivery_gps": "19.0760,72.8777",
            "quantity_mt": Decimal("2"),
            "price_inr": 44000,
            "commission_inr": 4000,
            "status": status,
        },
    )()


class _Contracts:
    def __init__(self, contract=None) -> None:
        self.contract = contract or _contract()

    async def get_by_transaction(self, transaction_id: str):
        return self.contract if transaction_id == self.contract.transaction_id else None


class _Callback:
    def __init__(self, fail: bool = False) -> None:
        self.sent = []
        self.fail = fail

    async def send(self, bap_uri: str, action: str, payload: dict) -> None:
        if self.fail:
            raise CallbackError("on_status callback failed")
        self.sent.append((action, payload))


async def test_status_returns_confirmed_order_state() -> None:
    callback = _Callback()
    service = StatusService(
        _Contracts(_contract("confirmed")),
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.status({"context": _context(), "message": {}})

    assert response.status_code == 200
    action, payload = callback.sent[0]
    assert action == "on_status"
    order = payload["message"]["order"]
    assert order["id"] == "ORD-txn-status-1"
    assert order["state"] == "Accepted"
    assert order["fulfillment"]["state"]["descriptor"]["code"] == "Order-confirmed"
    assert order["payment"]["status"] == "PAID-TO-ESCROW"
    assert order["tags"][0]["list"][1]["value"] == "confirmed"


async def test_status_returns_settled_order_state() -> None:
    callback = _Callback()
    service = StatusService(
        _Contracts(_contract("settled")),
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.status({"context": _context(), "message": {}})

    assert response.status_code == 200
    action, payload = callback.sent[0]
    assert action == "on_status"
    order = payload["message"]["order"]
    assert order["state"] == "Completed"
    assert order["fulfillment"]["state"]["descriptor"]["code"] == "Order-delivered"
    assert order["payment"]["status"] == "PAID-TO-SELLER"
    assert order["tags"][0]["list"][1]["value"] == "settled"


async def test_status_resolves_order_id_from_message() -> None:
    callback = _Callback()
    service = StatusService(
        _Contracts(_contract("confirmed")),
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )
    context = _context()

    response = await service.status({"context": context, "message": {"order_id": "ORD-txn-status-1"}})

    assert response.status_code == 200
    assert callback.sent[0][1]["message"]["order"]["id"] == "ORD-txn-status-1"


async def test_status_rejects_missing_contract() -> None:
    callback = _Callback()
    service = StatusService(
        _Contracts(_contract("confirmed")),
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )
    context = _context()
    context["transaction_id"] = "unknown-txn"

    response = await service.status({"context": context, "message": {}})

    assert response.status_code == 400
    assert response.body.decode().find("contract not found") != -1
    assert len(callback.sent) == 0


async def test_status_handles_callback_error() -> None:
    callback = _Callback(fail=True)
    service = StatusService(
        _Contracts(_contract("confirmed")),
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
    )

    response = await service.status({"context": _context(), "message": {}})

    assert response.status_code == 400
    assert response.body.decode().find("on_status callback failed") != -1


def test_status_route_rejects_wrong_action() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )
    context = _context()
    context["action"] = "confirm"
    with TestClient(application) as client:
        response = client.post("/beckn/status", json={"context": context, "message": {}})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "action must be status"
