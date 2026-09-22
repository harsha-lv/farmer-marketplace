from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api.consents import ConsentService, get_consent_service
from app.api.farmers import ProfileResolver
from app.config import Settings
from app.consent.models import ConsentArtifact
from app.consent.repository import ConsentRepository
from app.consent.schemas import ConsentGrantRequest, ConsentWithdrawalRequest
from app.consent.signing import (
    PURPOSE,
    ConsentRecord,
    authorize_profile_fetch,
    canonical_grant,
    canonical_withdrawal,
    sign,
)
from app.db.session import Database
from app.errors import AppError
from app.farmers.farm_id import make_farm_id
from app.farmers.repository import FarmerRepository
from app.farmers.ufsi import FarmerProfile, LandHolding
from app.main import create_app


SECRET = "consent-manager-secret"


def _grant_body(**overrides) -> dict:
    now = datetime(2026, 9, 21, tzinfo=UTC)
    body = {
        "artifact_id": "artifact-1",
        "farmer_id": "MH-100001",
        "purpose": PURPOSE,
        "attributes": ["land", "profile"],
        "created_at": now,
        "expires_at": now + timedelta(days=30),
    }
    body.update(overrides)
    payload = canonical_grant(
        artifact_id=body["artifact_id"],
        farmer_id=body["farmer_id"],
        purpose=body["purpose"],
        attributes=body["attributes"],
        created_at=body["created_at"],
        expires_at=body["expires_at"],
    )
    body["signature"] = sign(payload, SECRET)
    body["created_at"] = body["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
    body["expires_at"] = body["expires_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
    return body


def test_signature_rejects_a_changed_purpose() -> None:
    body = _grant_body()
    payload = canonical_grant(
        artifact_id=body["artifact_id"],
        farmer_id=body["farmer_id"],
        purpose="Some other purpose",
        attributes=body["attributes"],
        created_at=datetime(2026, 9, 21, tzinfo=UTC),
        expires_at=datetime(2026, 10, 21, tzinfo=UTC),
    )

    assert sign(payload, SECRET) != body["signature"]


def test_authorize_profile_fetch_enforces_purpose_and_farmer() -> None:
    now = datetime(2026, 9, 21, tzinfo=UTC)
    artifact = ConsentRecord(
        artifact_id="artifact-1",
        farmer_id="MH-100001",
        purpose=PURPOSE,
        attributes=("land", "profile"),
        created_at=now,
        expires_at=now + timedelta(days=1),
        status="active",
    )

    assert authorize_profile_fetch(artifact, "MH-100001", now) is None
    assert authorize_profile_fetch(None, "MH-100001", now) == "Consent is not active"
    assert authorize_profile_fetch(artifact, "MH-200002", now) == "Consent does not cover this farmer"
    expired = ConsentRecord(
        artifact_id=artifact.artifact_id,
        farmer_id=artifact.farmer_id,
        purpose=artifact.purpose,
        attributes=artifact.attributes,
        created_at=artifact.created_at,
        expires_at=now,
        status="active",
    )
    assert authorize_profile_fetch(expired, artifact.farmer_id, now) == "Consent has expired"


class _Consents:
    def __init__(self, artifact) -> None:
        self.artifact = artifact

    async def get(self, artifact_id: str):
        if self.artifact is not None and self.artifact.artifact_id == artifact_id:
            return self.artifact
        return None


class _Client:
    async def fetch_profile(self, **kwargs):
        raise AssertionError("registry was called")


class _Farmers:
    async def save(self, profile, consent_artifact_id: str):
        raise AssertionError("profile was stored")


class _Session:
    async def commit(self) -> None:
        raise AssertionError("session was committed")


async def test_profile_resolution_stops_before_the_registry_without_consent() -> None:
    resolver = ProfileResolver(_Client(), _Farmers(), _Consents(None), _Session())

    with pytest.raises(AppError) as caught:
        await resolver.resolve(
            type(
                "Request",
                (),
                {"farmer_id": "MH-100001", "state_lgd_code": "27", "consent_artifact_id": "missing"},
            )()
        )

    assert caught.value.status_code == 403
    assert caught.value.title == "Consent is not active"


def _application(secret: str = SECRET, ufsi: str = "") -> TestClient:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
            consent_signing_secret=secret,
            ufsi_base_url=ufsi,
        )
    )
    return TestClient(application)


def test_grant_requires_the_consent_manager_secret() -> None:
    with _application(secret="") as client:
        response = client.post("/api/v1/consents", json=_grant_body())

    assert response.status_code == 503
    assert response.json()["errors"][0]["title"] == "Consent manager is not configured"


def test_grant_rejects_a_bad_signature_without_echoing_it() -> None:
    body = _grant_body()
    body["signature"] = "a" * 64

    with _application() as client:
        response = client.post("/api/v1/consents", json=body)

    assert response.status_code == 401
    assert body["signature"] not in response.text


class _ConsentService:
    def __init__(self) -> None:
        self.granted = False

    async def grant(self, request):
        self.granted = True
        from app.consent.schemas import ConsentResponse

        return ConsentResponse(
            artifact_id=request.artifact_id,
            farmer_id=request.farmer_id,
            purpose=request.purpose,
            attributes=sorted(request.attributes),
            created_at=request.created_at,
            expires_at=request.expires_at,
            status="active",
            withdrawn_at=None,
        )

    async def withdraw(self, artifact_id: str, request):
        from app.consent.schemas import ConsentResponse

        return ConsentResponse(
            artifact_id=artifact_id,
            farmer_id="MH-100001",
            purpose=PURPOSE,
            attributes=["land", "profile"],
            created_at=datetime(2026, 9, 21, tzinfo=UTC),
            expires_at=datetime(2026, 10, 21, tzinfo=UTC),
            status="withdrawn",
            withdrawn_at=datetime(2026, 9, 22, tzinfo=UTC),
        )

    async def read(self, artifact_id: str):
        raise AppError(404, "Consent not found")


def test_grant_route_returns_the_active_artifact() -> None:
    service = _ConsentService()
    with _application() as client:
        client.app.dependency_overrides[get_consent_service] = lambda: service
        response = client.post("/api/v1/consents", json=_grant_body())

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert service.granted is True


def test_withdrawal_route_marks_the_artifact_withdrawn() -> None:
    body = {"signature": sign(canonical_withdrawal("artifact-1"), SECRET)}
    with _application() as client:
        client.app.dependency_overrides[get_consent_service] = lambda: _ConsentService()
        response = client.post("/api/v1/consents/artifact-1/withdrawals", json=body)

    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"
    assert body["signature"] not in response.text


async def test_withdrawal_deletes_the_profile_and_keeps_the_artifact() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    now = datetime(2026, 9, 21, tzinfo=UTC)
    farm_id = make_farm_id("27", "12345678901")
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.session_factory() as session:
            service = ConsentService(ConsentRepository(session), session, SECRET)
            granted = await service.grant(ConsentGrantRequest(**_grant_request(now)))
            farmers = FarmerRepository(session)
            await farmers.save(
                FarmerProfile(
                    farmer_id="MH-300003",
                    state_lgd_code="27",
                    display_name="Lakshmi",
                    parcels=[LandHolding(farm_id, None, [])],
                ),
                granted.artifact_id,
            )
            await session.commit()
            signature = sign(canonical_withdrawal(granted.artifact_id), SECRET)
            withdrawn = await service.withdraw(
                granted.artifact_id,
                ConsentWithdrawalRequest(signature=signature),
            )
            again = await service.withdraw(
                granted.artifact_id,
                ConsentWithdrawalRequest(signature=signature),
            )
            farmer = await farmers.get("MH-300003")
            await session.execute(
                delete(ConsentArtifact).where(ConsentArtifact.artifact_id == granted.artifact_id)
            )
            await session.commit()
    finally:
        await database.dispose()

    assert withdrawn.status == "withdrawn"
    assert again.status == "withdrawn"
    assert again.withdrawn_at == withdrawn.withdrawn_at
    assert farmer is None


def _grant_request(now: datetime) -> dict:
    expires = now + timedelta(days=30)
    payload = canonical_grant(
        artifact_id="artifact-db",
        farmer_id="MH-300003",
        purpose=PURPOSE,
        attributes=["profile", "land"],
        created_at=now,
        expires_at=expires,
    )
    return {
        "artifact_id": "artifact-db",
        "farmer_id": "MH-300003",
        "purpose": PURPOSE,
        "attributes": ["profile", "land"],
        "created_at": now,
        "expires_at": expires,
        "signature": sign(payload, SECRET),
    }
