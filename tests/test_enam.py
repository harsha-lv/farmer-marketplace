import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import Database
from app.lots.models import Lot
from app.lots.repository import LotRepository
from app.lots.schemas import LotCreateRequest

from app.api.lots import LotService, get_lot_service
from app.config import Settings
from app.errors import AppError
from app.lots.enam import EnamClient, EnamError
from app.lots.schemas import LotResponse
from app.main import create_app


async def test_client_opens_a_gate_and_then_creates_a_lot() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"path": request.url.path, "body": json.loads(request.content)})
        if request.url.path.endswith("/gate-entries"):
            return httpx.Response(200, json={"gate_id": "GATE-1", "secret": "hidden"})
        return httpx.Response(200, json={"lot_id": "ENAM-9"})

    client = EnamClient("https://enam.example", transport=httpx.MockTransport(handler))

    async def run():
        gate_id = await client.open_gate(
            lot_code="LOT-1",
            farmer_id="MH-400004",
            commodity="Onion",
            quantity_mt=Decimal("12.5"),
            grade="FAQ",
            mandi="Lasalgaon",
        )
        lot_id = await client.create_lot(
            gate_id=gate_id,
            lot_code="LOT-1",
            commodity="Onion",
            quantity_mt=Decimal("12.5"),
            grade="FAQ",
            variety="Red",
        )
        return gate_id, lot_id

    gate_id, lot_id = await run()

    assert (gate_id, lot_id) == ("GATE-1", "ENAM-9")
    assert seen[0]["path"] == "/gate-entries"
    assert seen[0]["body"]["mandi"] == "Lasalgaon"
    assert seen[1]["body"]["gate_id"] == "GATE-1"


async def test_client_hides_registry_error_bodies() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="token=secret-enam")

    client = EnamClient("https://enam.example", transport=httpx.MockTransport(handler))

    with pytest.raises(EnamError) as caught:
        await client.open_gate(
            lot_code="LOT-1",
            farmer_id="MH-400004",
            commodity="Onion",
            quantity_mt=Decimal("1"),
            grade="FAQ",
            mandi="Lasalgaon",
        )

    assert "secret-enam" not in str(caught.value)


class _Lot:
    def __init__(self) -> None:
        self.lot_code = "LOT-1"
        self.farmer_id = "MH-400004"
        self.commodity = "Onion"
        self.variety = "Red"
        self.quantity_mt = Decimal("12.5")
        self.consent_artifact_id = "artifact-lot"
        self.status = "assayed"
        self.created_at = datetime(2026, 9, 22, tzinfo=UTC)
        self.enam_gate_id = None
        self.enam_lot_id = None
        self.enam_registered_at = None
        self.assay = type("Assay", (), {"grade": "FAQ", "foreign_matter_percent": None, "moisture_percent": None, "damaged_percent": None, "recorded_at": self.created_at})()


class _Lots:
    def __init__(self, lot: _Lot | None) -> None:
        self.lot = lot

    async def get(self, lot_code: str):
        if self.lot is not None and self.lot.lot_code == lot_code:
            return self.lot
        return None

    async def assign_gate(self, lot: _Lot, gate_id: str) -> None:
        lot.enam_gate_id = gate_id

    async def assign_enam_lot(self, lot: _Lot, enam_lot_id: str) -> None:
        lot.enam_lot_id = enam_lot_id
        lot.status = "registered"
        lot.enam_registered_at = datetime.now(UTC)


class _Session:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def _farmer():
    return type("Farmer", (), {"farmer_id": "MH-400004", "consent_artifact_id": "artifact-lot"})()


def _artifact(status: str = "active"):
    now = datetime.now(UTC)
    return type(
        "Artifact",
        (),
        {
            "artifact_id": "artifact-lot",
            "farmer_id": "MH-400004",
            "purpose": "Market Linkage and Profile Verification",
            "attributes": ["land", "profile"],
            "created_at": now,
            "expires_at": now + timedelta(days=5),
            "status": status,
        },
    )()


class _Farmers:
    async def get(self, farmer_id: str):
        return _farmer() if farmer_id == "MH-400004" else None


class _Consents:
    def __init__(self, artifact) -> None:
        self.artifact = artifact

    async def get(self, artifact_id: str):
        if self.artifact is not None and self.artifact.artifact_id == artifact_id:
            return self.artifact
        return None


class _Enam:
    def __init__(self, fail_lot_once: bool = False) -> None:
        self.gates = 0
        self.lots = 0
        self.fail_lot_once = fail_lot_once

    async def open_gate(self, **kwargs) -> str:
        self.gates += 1
        return "GATE-1"

    async def create_lot(self, **kwargs) -> str:
        self.lots += 1
        if self.fail_lot_once and self.lots == 1:
            raise EnamError("market registry returned 503")
        return "ENAM-9"


async def test_registration_retries_lot_creation_without_a_second_gate() -> None:
    lot = _Lot()
    enam = _Enam(fail_lot_once=True)
    service = LotService(_Session(), _Farmers(), _Consents(_artifact()), _Lots(lot), enam)

    with pytest.raises(AppError) as caught:
        await service.register("LOT-1", "Lasalgaon")

    assert caught.value.status_code == 502
    assert lot.enam_gate_id == "GATE-1"
    assert lot.enam_lot_id is None

    registered = await service.register("LOT-1", "Lasalgaon")

    assert registered.enam_lot_id == "ENAM-9"
    assert registered.status == "registered"
    assert enam.gates == 1
    assert enam.lots == 2


async def test_registration_does_not_call_the_registry_twice() -> None:
    lot = _Lot()
    lot.enam_gate_id = "GATE-1"
    lot.enam_lot_id = "ENAM-9"
    lot.status = "registered"
    enam = _Enam()
    service = LotService(_Session(), _Farmers(), _Consents(_artifact()), _Lots(lot), enam)

    registered = await service.register("LOT-1", "Lasalgaon")

    assert registered.enam_lot_id == "ENAM-9"
    assert enam.gates == 0
    assert enam.lots == 0


async def test_registration_stops_when_consent_is_withdrawn() -> None:
    enam = _Enam()
    service = LotService(_Session(), _Farmers(), _Consents(_artifact("withdrawn")), _Lots(_Lot()), enam)

    with pytest.raises(AppError) as caught:
        await service.register("LOT-1", "Lasalgaon")

    assert caught.value.status_code == 403
    assert enam.gates == 0


def test_registration_route_requires_a_configured_registry() -> None:
    class Service:
        async def register(self, lot_code: str, mandi: str) -> LotResponse:
            raise AppError(503, "Market registry is not configured")

    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )
    application.dependency_overrides[get_lot_service] = lambda: Service()
    with TestClient(application) as client:
        response = client.post("/api/v1/lots/LOT-1/enam-registration", json={"mandi": "Lasalgaon"})

    assert response.status_code == 503
    assert response.json()["errors"][0]["title"] == "Market registry is not configured"


async def test_repository_persists_enam_ids() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.session_factory() as session:
            repository = LotRepository(session)
            created = await repository.create(
                LotCreateRequest(
                    farmer_id="MH-400004",
                    consent_artifact_id="artifact-lot",
                    commodity="Onion",
                    quantity_mt=Decimal("1.5"),
                    grade="FAQ",
                )
            )
            await repository.assign_gate(created, "GATE-1")
            await repository.assign_enam_lot(created, "ENAM-9")
            await session.commit()
            loaded = await repository.get(created.lot_code)
            gate_id = None if loaded is None else loaded.enam_gate_id
            enam_lot_id = None if loaded is None else loaded.enam_lot_id
            status = None if loaded is None else loaded.status
            await session.execute(delete(Lot).where(Lot.lot_code == created.lot_code))
            await session.commit()
    finally:
        await database.dispose()

    assert gate_id == "GATE-1"
    assert enam_lot_id == "ENAM-9"
    assert status == "registered"
