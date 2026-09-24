from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, SettingsDep
from app.consent.anonymization import AnonymizationEngine
from app.consent.models import ConsentArtifact
from app.consent.repository import ConsentRepository, utcnow
from app.consent.schemas import (
    ConsentAuditResponse,
    ConsentGrantRequest,
    ConsentResponse,
    ConsentWebhookRequest,
    ConsentWithdrawalRequest,
    ErasureCertificateResponse,
)
from app.consent.signing import (
    PROFILE_ATTRIBUTES,
    PURPOSE,
    canonical_cm_webhook,
    canonical_grant,
    canonical_withdrawal,
    mask_farmer_id,
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
            engine = AnonymizationEngine(self.session, self.secret)
            await engine.execute_cascaded_anonymization(
                artifact,
                reason="Consent withdrawn by Data Principal",
                event_source="data_principal_withdrawal",
            )
        return consent_response(artifact)

    async def handle_webhook(self, request: ConsentWebhookRequest) -> ErasureCertificateResponse:
        self._require_secret()
        canonical = canonical_cm_webhook(
            event_id=request.event_id,
            event_type=request.event_type,
            artifact_id=request.artifact_id,
            farmer_id=request.farmer_id,
            timestamp=request.timestamp,
        )
        if not signature_matches(canonical, request.signature, self.secret):
            raise AppError(401, "Consent manager webhook signature is invalid")

        artifact = await self.repository.get(request.artifact_id)
        if artifact is None:
            raise AppError(404, "Consent artifact not found")

        if artifact.farmer_id != request.farmer_id:
            raise AppError(422, "Invalid request", "farmer_id does not match consent artifact")

        engine = AnonymizationEngine(self.session, self.secret)
        cert = await engine.execute_cascaded_anonymization(
            artifact,
            reason=request.reason or f"Consent Manager notification: {request.event_type}",
            event_source=f"cm_webhook:{request.event_id}",
        )
        return cert

    async def anonymize(self, artifact_id: str, reason: str | None = None) -> ErasureCertificateResponse:
        self._require_secret()
        artifact = await self.repository.get(artifact_id)
        if artifact is None:
            raise AppError(404, "Consent artifact not found")

        engine = AnonymizationEngine(self.session, self.secret)
        cert = await engine.execute_cascaded_anonymization(
            artifact,
            reason=reason or "Manual DPDP data subject erasure requested",
            event_source="manual_erasure_request",
        )
        return cert

    async def audit(self, artifact_id: str) -> ConsentAuditResponse:
        artifact = await self.repository.get(artifact_id)
        if artifact is None:
            raise AppError(404, "Consent not found")

        events = await EventRepository(self.session).get_by_consent(artifact_id)
        events_data = [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "occurred_at": e.occurred_at.isoformat(),
                "payload": e.payload,
            }
            for e in events
        ]

        cert_data: ErasureCertificateResponse | None = None
        for e in events:
            if e.event_type == "DataSubjectErasureCompleted" and isinstance(e.payload, dict):
                p = e.payload
                cert_data = ErasureCertificateResponse(
                    certificate_id=p.get("certificate_id", ""),
                    farmer_id=p.get("masked_farmer_id", mask_farmer_id(artifact.farmer_id)),
                    artifact_id=artifact.artifact_id,
                    status="ANONYMIZED_AND_PURGED",
                    reason="Data erasure completed and audited",
                    parcels_purged=p.get("parcels_purged", 0),
                    lots_withdrawn=p.get("lots_withdrawn", 0),
                    withdrawn_lot_codes=[],
                    cache_keys_evicted=p.get("cache_keys_evicted", []),
                    verification_hash=p.get("verification_hash", ""),
                    timestamp=e.occurred_at,
                )
                break

        return ConsentAuditResponse(
            artifact_id=artifact.artifact_id,
            farmer_id=artifact.farmer_id,
            purpose=artifact.purpose,
            attributes=list(artifact.attributes),
            created_at=artifact.created_at,
            expires_at=artifact.expires_at,
            status=artifact.status,
            withdrawn_at=artifact.withdrawn_at,
            erasure_certificate=cert_data,
            audit_events=events_data,
        )

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


@router.post("/webhook")
async def consent_webhook(
    body: ConsentWebhookRequest,
    service: ConsentServiceDep,
) -> ErasureCertificateResponse:
    return await service.handle_webhook(body)


@router.post("/{artifact_id}/withdrawals")
async def withdraw_consent(
    artifact_id: str,
    body: ConsentWithdrawalRequest,
    service: ConsentServiceDep,
) -> ConsentResponse:
    return await service.withdraw(artifact_id, body)


@router.post("/{artifact_id}/anonymize")
async def trigger_anonymization(
    artifact_id: str,
    service: ConsentServiceDep,
) -> ErasureCertificateResponse:
    return await service.anonymize(artifact_id)


@router.get("/{artifact_id}")
async def read_consent(artifact_id: str, service: ConsentServiceDep) -> ConsentResponse:
    return await service.read(artifact_id)


@router.get("/{artifact_id}/audit")
async def audit_consent(
    artifact_id: str,
    service: ConsentServiceDep,
) -> ConsentAuditResponse:
    return await service.audit(artifact_id)


root_consent_router = APIRouter(tags=["consents"])


@root_consent_router.post("/consents/webhook")
async def root_consent_webhook(
    body: ConsentWebhookRequest,
    service: ConsentServiceDep,
) -> ErasureCertificateResponse:
    return await service.handle_webhook(body)
