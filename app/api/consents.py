from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, SettingsDep
from app.consent.models import ConsentArtifact
from app.consent.repository import ConsentRepository, utcnow
from app.consent.schemas import ConsentGrantRequest, ConsentResponse, ConsentWithdrawalRequest
from app.consent.signing import (
    PROFILE_ATTRIBUTES,
    PURPOSE,
    canonical_grant,
    canonical_withdrawal,
    signature_matches,
)
from app.errors import AppError
from app.events.repository import EventRepository

router = APIRouter(prefix="/consents", tags=["consents"])


def consent_response(artifact: ConsentArtifact) -> ConsentResponse:
    return ConsentResponse(
        artifact_id=artifact.artifact_id,
        farmer_id=artifact.farmer_id,
        purpose=artifact.purpose,
        attributes=list(artifact.attributes),
        created_at=artifact.created_at,
        expires_at=artifact.expires_at,
        status=artifact.status,
        withdrawn_at=artifact.withdrawn_at,
    )


class ConsentService:
    def __init__(self, repository: ConsentRepository, session: AsyncSession, secret: str) -> None:
        self.repository = repository
        self.session = session
        self.secret = secret

    async def grant(self, request: ConsentGrantRequest) -> ConsentResponse:
        self._require_secret()
        if request.purpose != PURPOSE:
            raise AppError(422, "Invalid request", f"purpose must be {PURPOSE}")
        if not PROFILE_ATTRIBUTES <= set(request.attributes):
            raise AppError(422, "Invalid request", "attributes must include profile and land")
        if request.expires_at <= request.created_at or request.expires_at <= utcnow():
            raise AppError(422, "Invalid request", "consent must expire in the future")
        payload = canonical_grant(
            artifact_id=request.artifact_id,
            farmer_id=request.farmer_id,
            purpose=request.purpose,
            attributes=request.attributes,
            created_at=request.created_at,
            expires_at=request.expires_at,
        )
        if not signature_matches(payload, request.signature, self.secret):
            raise AppError(401, "Consent signature is invalid")
        existing = await self.repository.get(request.artifact_id)
        if existing is not None:
            if not _same_grant(existing, request):
                raise AppError(409, "Consent artifact already exists")
            return consent_response(existing)
        artifact = ConsentArtifact(
            artifact_id=request.artifact_id,
            farmer_id=request.farmer_id,
            purpose=request.purpose,
            attributes=sorted(set(request.attributes)),
            created_at=request.created_at,
            expires_at=request.expires_at,
            recorded_at=utcnow(),
            status="active",
            withdrawn_at=None,
            signature=request.signature,
        )
        await self.repository.add(artifact)
        await EventRepository(self.session).record_event(
            event_type="ConsentGranted",
            stream_id=f"consent:{artifact.artifact_id}",
            partition_key=artifact.farmer_id,
            payload={
                "artifact_id": artifact.artifact_id,
                "farmer_id": artifact.farmer_id,
                "purpose": artifact.purpose,
                "attributes": artifact.attributes,
                "expires_at": artifact.expires_at.isoformat(),
            },
            consent_artifact_id=artifact.artifact_id,
        )
        await self.session.commit()
        return consent_response(artifact)

    async def withdraw(self, artifact_id: str, request: ConsentWithdrawalRequest) -> ConsentResponse:
        self._require_secret()
        if not signature_matches(canonical_withdrawal(artifact_id), request.signature, self.secret):
            raise AppError(401, "Consent signature is invalid")
        artifact = await self.repository.get(artifact_id)
        if artifact is None:
            raise AppError(404, "Consent not found")
        if artifact.status != "withdrawn":
            artifact.status = "withdrawn"
            artifact.withdrawn_at = utcnow()
            await self.repository.delete_profile(artifact.farmer_id, artifact.artifact_id)
            await EventRepository(self.session).record_event(
                event_type="ConsentRevoked",
                stream_id=f"consent:{artifact.artifact_id}",
                partition_key=artifact.farmer_id,
                payload={
                    "artifact_id": artifact.artifact_id,
                    "farmer_id": artifact.farmer_id,
                    "withdrawn_at": artifact.withdrawn_at.isoformat(),
                },
                consent_artifact_id=artifact.artifact_id,
            )
            await self.session.commit()
        return consent_response(artifact)

    async def read(self, artifact_id: str) -> ConsentResponse:
        artifact = await self.repository.get(artifact_id)
        if artifact is None:
            raise AppError(404, "Consent not found")
        return consent_response(artifact)

    def _require_secret(self) -> None:
        if not self.secret:
            raise AppError(503, "Consent manager is not configured")


def _same_grant(existing: ConsentArtifact, request: ConsentGrantRequest) -> bool:
    return (
        existing.farmer_id == request.farmer_id
        and existing.purpose == request.purpose
        and set(existing.attributes) == set(request.attributes)
        and existing.expires_at == request.expires_at
        and existing.signature == request.signature
    )


def get_consent_service(session: SessionDep, settings: SettingsDep) -> ConsentService:
    return ConsentService(ConsentRepository(session), session, settings.consent_signing_secret)


ConsentServiceDep = Annotated[ConsentService, Depends(get_consent_service)]


@router.post("")
async def grant_consent(body: ConsentGrantRequest, service: ConsentServiceDep) -> ConsentResponse:
    return await service.grant(body)


@router.post("/{artifact_id}/withdrawals")
async def withdraw_consent(
    artifact_id: str,
    body: ConsentWithdrawalRequest,
    service: ConsentServiceDep,
) -> ConsentResponse:
    return await service.withdraw(artifact_id, body)


@router.get("/{artifact_id}")
async def read_consent(artifact_id: str, service: ConsentServiceDep) -> ConsentResponse:
    return await service.read(artifact_id)
