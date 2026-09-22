import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api.farmers import get_farmer_repository, get_resolver
from app.config import Settings
from app.db.session import Database
from app.farmers.farm_id import FarmIdError, make_farm_id, validate_farm_id
from app.farmers.models import Farmer
from app.farmers.repository import FarmerRepository
from app.farmers.schemas import FarmerProfileResponse, ParcelResponse
from app.farmers.ufsi import FarmerProfile, LandHolding, ParcelCrop, RegistryError, UfsiClient, parse_profile
from app.main import create_app


def test_farm_id_checksum_round_trip() -> None:
    farm_id = make_farm_id("7", "12345678901")

    assert len(farm_id) == 14
    assert farm_id.startswith("07")
    assert validate_farm_id(farm_id, state_lgd_code="07") == farm_id
    with pytest.raises(FarmIdError):
        validate_farm_id(farm_id[:-1] + ("0" if farm_id[-1] != "0" else "1"), state_lgd_code="7")
    with pytest.raises(FarmIdError):
        validate_farm_id(farm_id, state_lgd_code="27")


def test_profile_parser_reads_a_json_api_document() -> None:
    farm_id = make_farm_id("27", "12345678901")
    profile = parse_profile(
        {
            "data": {
                "type": "farmer-profiles",
                "attributes": {
                    "displayName": "Lakshmi",
                    "parcels": [
                        {
                            "farmId": farm_id,
                            "areaHectares": "1.25",
                            "crops": [{"commodity": "Onion", "season": "rabi"}],
                        }
                    ],
                },
            }
        },
        farmer_id="MH-100001",
        state_lgd_code="27",
    )

    assert profile.display_name == "Lakshmi"
    assert profile.parcels[0].farm_id == farm_id
    assert profile.parcels[0].area_hectares == Decimal("1.25")
    assert profile.parcels[0].crops[0].season == "rabi"


def test_profile_parser_rejects_an_invalid_farm_id() -> None:
    farm_id = make_farm_id("27", "12345678901")
    broken = farm_id[:2] + ("0" if farm_id[2] != "0" else "1") + farm_id[3:]

    with pytest.raises(RegistryError):
        parse_profile(
            {
                "data": {
                    "attributes": {
                        "displayName": "Lakshmi",
                        "parcels": [{"farmId": broken}],
                    }
                }
            },
            farmer_id="MH-100001",
            state_lgd_code="27",
        )


async def test_client_sends_the_consent_artifact_and_not_an_identity_number() -> None:
    farm_id = make_farm_id("27", "12345678901")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["content_type"] = request.headers["content-type"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": {
                    "type": "farmer-profiles",
                    "attributes": {"displayName": "Lakshmi", "parcels": [{"farmId": farm_id}]},
                }
            },
        )

    client = UfsiClient("https://registry.example", transport=httpx.MockTransport(handler))
    profile = await client.fetch_profile(
        farmer_id="MH-100001",
        state_lgd_code="27",
        consent_artifact_id="artifact-1",
    )

    assert profile.display_name == "Lakshmi"
    assert seen["path"] == "/farmerProfileById"
    assert seen["content_type"] == "application/vnd.api+json"
    attributes = seen["body"]["data"]["attributes"]
    assert attributes == {
        "farmerId": "MH-100001",
        "stateLgdCode": "27",
        "consentArtifact": "artifact-1",
    }
    assert "aadhaar" not in json.dumps(seen["body"]).casefold()


def _settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "log_level": "WARNING",
        "database_url": "postgresql+asyncpg://app:app@127.0.0.1:1/app",
        "ufsi_base_url": "",
    }
    values.update(overrides)
    return Settings(**values)


def test_resolve_requires_a_configured_registry() -> None:
    application = create_app(_settings())
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/farmers/profile",
            json={
                "farmer_id": "MH-100001",
                "state_lgd_code": "27",
                "consent_artifact_id": "artifact-1",
            },
        )

    assert response.status_code == 503
    assert response.json()["errors"][0]["title"] == "Farmer registry is not configured"


def test_resolve_rejects_a_missing_consent_artifact() -> None:
    application = create_app(_settings(ufsi_base_url="https://registry.example"))
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/farmers/profile",
            json={"farmer_id": "MH-100001", "state_lgd_code": "27"},
        )

    assert response.status_code == 422
    assert response.json()["errors"][0]["source"]["pointer"] == "/body/consent_artifact_id"


class _Resolver:
    def __init__(self) -> None:
        self.requests = []

    async def resolve(self, request) -> FarmerProfileResponse:
        self.requests.append(request)
        return FarmerProfileResponse(
            farmer_id=request.farmer_id,
            state_lgd_code=request.state_lgd_code,
            display_name="Lakshmi",
            consent_artifact_id=request.consent_artifact_id,
            fetched_at=datetime(2026, 9, 21, tzinfo=UTC),
            parcels=[
                ParcelResponse(farm_id=make_farm_id("27", "12345678901"), area_hectares=None, crops=[])
            ],
        )


def test_resolve_route_returns_the_stored_shape() -> None:
    resolver = _Resolver()
    application = create_app(_settings(ufsi_base_url="https://registry.example"))
    application.dependency_overrides[get_resolver] = lambda: resolver
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/farmers/profile",
            json={
                "farmer_id": "MH-100001",
                "state_lgd_code": "07",
                "consent_artifact_id": "artifact-1",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Lakshmi"
    assert body["state_lgd_code"] == "7"
    assert resolver.requests[0].consent_artifact_id == "artifact-1"


class _Repository:
    def __init__(self, farmer: FarmerProfileResponse | None) -> None:
        self.farmer = farmer

    async def get(self, farmer_id: str):
        return self.farmer


def test_read_farmer_uses_the_stored_record() -> None:
    application = create_app(_settings())
    application.dependency_overrides[get_farmer_repository] = lambda: _Repository(None)
    with TestClient(application) as client:
        missing = client.get("/api/v1/farmers/MH-100001")

    assert missing.status_code == 404
    assert missing.json()["errors"][0]["title"] == "Farmer not found"


async def test_repository_replaces_parcels_on_a_later_fetch() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    first_farm = make_farm_id("27", "12345678901")
    second_farm = make_farm_id("27", "10987654321")
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.session_factory() as session:
            repository = FarmerRepository(session)
            await repository.save(
                FarmerProfile(
                    farmer_id="MH-100001",
                    state_lgd_code="27",
                    display_name="Lakshmi",
                    parcels=[
                        LandHolding(first_farm, Decimal("1.25"), [ParcelCrop("Onion", "rabi")])
                    ],
                ),
                "artifact-1",
            )
            saved = await repository.save(
                FarmerProfile(
                    farmer_id="MH-100001",
                    state_lgd_code="27",
                    display_name="Lakshmi Devi",
                    parcels=[LandHolding(second_farm, None, [ParcelCrop("Wheat", "kharif")])],
                ),
                "artifact-2",
            )
            await session.commit()
            loaded = await repository.get("MH-100001")
            assert loaded is not None
            name = loaded.display_name
            consent = loaded.consent_artifact_id
            farm_ids = sorted(parcel.farm_id for parcel in loaded.parcels)
            seasons = [crop.season for parcel in loaded.parcels for crop in parcel.crops]
            await session.execute(delete(Farmer).where(Farmer.farmer_id == "MH-100001"))
            await session.commit()
    finally:
        await database.dispose()

    assert name == "Lakshmi Devi"
    assert consent == "artifact-2"
    assert farm_ids == [second_farm]
    assert seasons == ["kharif"]
