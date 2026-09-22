from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api.consents import ConsentService
from app.api.lots import LotService, get_lot_service
from app.config import Settings
from app.consent.models import ConsentArtifact
from app.consent.repository import ConsentRepository
from app.consent.schemas import ConsentGrantRequest
from app.consent.signing import PURPOSE, canonical_grant, sign
from app.db.session import Database
from app.errors import AppError
from app.farmers.models import Farmer
from app.farmers.repository import FarmerRepository
from app.farmers.ufsi import FarmerProfile
from app.lots.models import Lot
from app.lots.repository import LotRepository
from app.lots.schemas import LotCreateRequest, LotResponse
from app.main import create_app

SECRET = "consent-manager-secret"


def test_lot_request_rejects_a_percentage_above_one_hundred() -> None:
    with pytest.raises(ValueError):
        LotCreateRequest(
            farmer_id="MH-300003",
            consent_artifact_id="artifact-db",
            commodity="Onion",
            quantity_mt=Decimal("1.5"),
            grade="FAQ",
            moisture_percent=Decimal("101"),
        )


class _Farmers:
    def __init__(self, farmer) -> None:
        self.farmer = farmer

    async def get(self, farmer_id: str):
        if self.farmer is not None and self.farmer.farmer_id == farmer_id:
            return self.farmer
        return None


class _Consents:
    def __init__(self, artifact) -> None:
        self.artifact = artifact

    async def get(self, artifact_id: str):
        if self.artifact is not None and self.artifact.artifact_id == artifact_id:
            return self.artifact
        return None


class _Lots:
    def __init__(self) -> None:
        self.created = None

    async def create(self, request: LotCreateRequest):
        raise AssertionError("lot was created")


class _Session:
    async def commit(self) -> None:
        raise AssertionError("committed")


def _artifact(farmer_id: str = "MH-300003", status: str = "active"):
    now = datetime.now(UTC)
    return type(
        "Artifact",
        (),
        {
            "artifact_id": "artifact-db",
            "farmer_id": farmer_id,
            "purpose": PURPOSE,
            "attributes": ["land", "profile"],
            "created_at": now,
            "expires_at": now + timedelta(days=10),
            "status": status,
        },
    )()


def _farmer(consent_id: str = "artifact-db"):
    return type("Farmer", (), {"farmer_id": "MH-300003", "consent_artifact_id": consent_id})()


def _request() -> LotCreateRequest:
    return LotCreateRequest(
        farmer_id="MH-300003",
        consent_artifact_id="artifact-db",
        commodity="Onion",
        quantity_mt=Decimal("12.5"),
        grade="FAQ",
        moisture_percent=Decimal("12"),
    )


async def test_create_lot_refuses_an_unknown_farmer() -> None:
    service = LotService(_Session(), _Farmers(None), _Consents(_artifact()), _Lots(), None)

    with pytest.raises(AppError) as caught:
        await service.create(_request())

    assert caught.value.status_code == 404
    assert caught.value.title == "Farmer not found"


async def test_create_lot_refuses_a_consent_that_does_not_match_the_profile() -> None:
    service = LotService(_Session(), _Farmers(_farmer("other-artifact")), _Consents(_artifact()), _Lots(), None)

    with pytest.raises(AppError) as caught:
        await service.create(_request())

    assert caught.value.status_code == 403
    assert caught.value.title == "Consent does not match the stored profile"


def test_create_route_returns_the_assayed_lot() -> None:
    recorded: dict = {}

    class Service:
        async def create(self, request: LotCreateRequest) -> LotResponse:
            recorded["commodity"] = request.commodity
            return LotResponse(
                lot_code="LOT-TEST",
                farmer_id=request.farmer_id,
                commodity=request.commodity,
                variety="",
                quantity_mt=request.quantity_mt,
                consent_artifact_id=request.consent_artifact_id,
                status="assayed",
                created_at=datetime(2026, 9, 22, tzinfo=UTC),
                assay={
                    "grade": request.grade,
                    "foreign_matter_percent": None,
                    "moisture_percent": request.moisture_percent,
                    "damaged_percent": None,
                    "recorded_at": datetime(2026, 9, 22, tzinfo=UTC),
                },
            )

        async def read(self, lot_code: str) -> LotResponse:
            raise AppError(404, "Lot not found")

        async def list_for_farmer(self, farmer_id: str) -> dict:
            return {"data": []}

    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )
    application.dependency_overrides[get_lot_service] = lambda: Service()
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/lots",
            json={
                "farmer_id": "MH-300003",
                "consent_artifact_id": "artifact-db",
                "commodity": "Onion",
                "quantity_mt": "12.5",
                "grade": "FAQ",
                "moisture_percent": "12",
            },
        )

    assert response.status_code == 200
    assert response.json()["lot_code"] == "LOT-TEST"
    assert response.json()["assay"]["grade"] == "FAQ"
    assert recorded["commodity"] == "Onion"


async def test_repository_stores_an_assayed_lot_for_a_consented_farmer() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    now = datetime(2026, 9, 22, tzinfo=UTC)
    expires = now + timedelta(days=30)
    payload = canonical_grant(
        artifact_id="artifact-lot",
        farmer_id="MH-400004",
        purpose=PURPOSE,
        attributes=["profile", "land"],
        created_at=now,
        expires_at=expires,
    )
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.session_factory() as session:
            consents = ConsentService(ConsentRepository(session), session, SECRET)
            await consents.grant(
                ConsentGrantRequest(
                    artifact_id="artifact-lot",
                    farmer_id="MH-400004",
                    purpose=PURPOSE,
                    attributes=["profile", "land"],
                    created_at=now,
                    expires_at=expires,
                    signature=sign(payload, SECRET),
                )
            )
            await FarmerRepository(session).save(
                FarmerProfile(
                    farmer_id="MH-400004",
                    state_lgd_code="27",
                    display_name="Lakshmi",
                    parcels=[],
                ),
                "artifact-lot",
            )
            await session.commit()
            created = await LotService(
                session,
                FarmerRepository(session),
                ConsentRepository(session),
                LotRepository(session),
                None,
            ).create(
                LotCreateRequest(
                    farmer_id="MH-400004",
                    consent_artifact_id="artifact-lot",
                    commodity="Onion",
                    quantity_mt=Decimal("12.500"),
                    grade="FAQ",
                    foreign_matter_percent=Decimal("1.5"),
                )
            )
            loaded = await LotRepository(session).get(created.lot_code)
            listed = await LotRepository(session).list_for_farmer("MH-400004")
            await session.execute(delete(Lot).where(Lot.farmer_id == "MH-400004"))
            await session.execute(delete(Farmer).where(Farmer.farmer_id == "MH-400004"))
            await session.execute(delete(ConsentArtifact).where(ConsentArtifact.artifact_id == "artifact-lot"))
            await session.commit()
    finally:
        await database.dispose()

    assert created.status == "assayed"
    assert created.assay.grade == "FAQ"
    assert created.assay.foreign_matter_percent == Decimal("1.50")
    assert loaded is not None
    assert [lot.lot_code for lot in listed] == [created.lot_code]
