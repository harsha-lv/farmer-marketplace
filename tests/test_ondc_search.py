from datetime import UTC, datetime, timedelta
from decimal import Decimal

import json

import pytest
from fastapi.testclient import TestClient

from app.api.beckn import SearchService
from app.config import Settings
from app.db.session import Database
from app.lots.models import Lot
from app.lots.repository import LotRepository
from app.lots.schemas import LotCreateRequest
from app.main import create_app
from app.ondc.callback import CallbackError, callback_url
from app.ondc.catalog import build_catalog, grade_matches
from sqlalchemy import delete


def _context(**overrides) -> dict:
    context = {
        "domain": "ONDC:AGR10",
        "action": "search",
        "version": "2.0.0",
        "bap_id": "buyer.example",
        "bap_uri": "https://buyer.example/beckn",
        "transaction_id": "txn-1",
        "message_id": "msg-1",
        "timestamp": "2026-09-22T00:00:00Z",
    }
    context.update(overrides)
    return context


def _lot(code: str, commodity: str = "Onion", grade: str = "FAQ", enam: str | None = "ENAM-1", receipt: str | None = None):
    now = datetime(2026, 9, 22, tzinfo=UTC)
    lot = type("Lot", (), {})()
    lot.lot_code = code
    lot.farmer_id = "MH-400004"
    lot.commodity = commodity
    lot.quantity_mt = Decimal("12.5")
    lot.enam_lot_id = enam
    lot.warehouse_receipt_id = receipt
    lot.consent_artifact_id = "artifact-lot"
    lot.assay = type("Assay", (), {"grade": grade})()
    lot.created_at = now
    return lot


def test_grade_match_accepts_a_more_specific_buyer_code() -> None:
    assert grade_matches("FAQ", "FAQ-Grade-A")
    assert not grade_matches("Medium", "FAQ")


def test_catalog_groups_items_by_farmer_and_keeps_the_receipt() -> None:
    catalog = build_catalog([_lot("LOT-1", receipt="ENWR-4")], "Market desk")

    provider = catalog["bpp/providers"][0]
    assert provider["id"] == "MH-400004"
    assert provider["items"][0]["id"] == "LOT-1"
    assert provider["items"][0]["tags"][-1] == {"code": "warehouse_receipt_id", "value": "ENWR-4"}
    assert catalog["bpp/descriptor"]["name"] == "Market desk"


def test_callback_url_rejects_private_hosts() -> None:
    with pytest.raises(CallbackError):
        callback_url("http://127.0.0.1/beckn")
    with pytest.raises(CallbackError):
        callback_url("http://169.254.169.254/latest")
    assert callback_url("https://8.8.8.8/beckn") == "https://8.8.8.8/on_search"


class _Lots:
    def __init__(self, lots: list) -> None:
        self.lots = lots

    async def list_registered(self, commodity: str | None) -> list:
        if commodity is None:
            return self.lots
        return [lot for lot in self.lots if lot.commodity.casefold() == commodity.casefold()]


class _Farmers:
    async def get(self, farmer_id: str):
        if farmer_id == "MH-400004":
            return type("Farmer", (), {"farmer_id": farmer_id, "consent_artifact_id": "artifact-lot"})()
        return None


class _Consents:
    def __init__(self, status: str = "active") -> None:
        self.status = status

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
                "expires_at": now + timedelta(days=3),
                "status": self.status,
            },
        )()


class _Callback:
    def __init__(self, fail: bool = False) -> None:
        self.payloads: list[dict] = []
        self.fail = fail

    async def on_search(self, bap_uri: str, payload: dict) -> None:
        if self.fail:
            raise CallbackError("on_search callback failed")
        self.payloads.append({"uri": bap_uri, "payload": payload})


def _service(lots: list, callback: _Callback, status: str = "active") -> SearchService:
    return SearchService(
        _Lots(lots),
        _Farmers(),
        _Consents(status),
        callback,
        bpp_id="market.local",
        bpp_uri="http://market.local/beckn",
        bpp_name="Market desk",
    )


async def test_search_sends_only_the_matching_registered_lot() -> None:
    callback = _Callback()
    service = _service(
        [
            _lot("LOT-ONION"),
            _lot("LOT-WHEAT", commodity="Wheat"),
            _lot("LOT-MEDIUM", grade="Medium"),
        ],
        callback,
    )

    response = await service.search(
        {
            "context": _context(),
            "message": {"intent": {"item": {"descriptor": {"name": "Onion", "code": "FAQ"}}}},
        }
    )

    assert response.status_code == 200
    assert response.body
    sent = callback.payloads[0]["payload"]
    assert sent["context"]["action"] == "on_search"
    assert sent["context"]["transaction_id"] == "txn-1"
    items = sent["message"]["catalog"]["bpp/providers"][0]["items"]
    assert [item["id"] for item in items] == ["LOT-ONION"]


async def test_search_omits_a_lot_whose_consent_was_withdrawn() -> None:
    callback = _Callback()
    service = _service([_lot("LOT-ONION")], callback, status="withdrawn")

    response = await service.search({"context": _context(), "message": {}})

    assert response.status_code == 200
    assert callback.payloads[0]["payload"]["message"]["catalog"]["bpp/providers"] == []


async def test_search_nacks_when_the_callback_fails() -> None:
    service = _service([_lot("LOT-ONION")], _Callback(fail=True))

    response = await service.search({"context": _context(), "message": {}})

    assert response.status_code == 400
    assert json.loads(response.body)["error"]["message"] == "on_search callback failed"


def test_search_route_nacks_an_unsupported_domain() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )
    with TestClient(application) as client:
        response = client.post("/beckn/search", json={"context": _context(domain="ONDC:RET10"), "message": {}})

    assert response.status_code == 400
    assert response.json()["message"]["ack"]["status"] == "NACK"


async def test_registered_lots_are_the_only_rows_offered() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.session_factory() as session:
            repository = LotRepository(session)
            registered = await repository.create(
                LotCreateRequest(
                    farmer_id="MH-500005",
                    consent_artifact_id="artifact-search",
                    commodity="Onion",
                    quantity_mt=Decimal("2"),
                    grade="FAQ",
                )
            )
            await repository.assign_enam_lot(registered, "ENAM-SEARCH")
            plain = await repository.create(
                LotCreateRequest(
                    farmer_id="MH-500005",
                    consent_artifact_id="artifact-search",
                    commodity="Onion",
                    quantity_mt=Decimal("1"),
                    grade="FAQ",
                )
            )
            await session.commit()
            found = await repository.list_registered("onion")
            codes = {lot.lot_code for lot in found}
            await session.execute(delete(Lot).where(Lot.farmer_id == "MH-500005"))
            await session.commit()
    finally:
        await database.dispose()

    assert registered.lot_code in codes
    assert plain.lot_code not in codes
