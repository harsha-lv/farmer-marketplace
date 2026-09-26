import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    SessionDep,
    SettingsDep,
    get_current_user,
    require_org_access,
    require_roles,
)
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

logger = logging.getLogger("app.api.consents")

# Maximum clock skew tolerated on inbound webhook timestamps (seconds)
_MAX_SKEW_SECONDS = 300
# Redis TTL for delivery-id idempotency key (24 hours)
_REPLAY_TTL_SECONDS = 86_400

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

    async def process_cm_webhook(
        self,
        raw_body: bytes,
        *,
        delivery_id: str | None = None,
        signature_header: str | None = None,
        webhook_secret: str,
        cache_client: object | None = None,
        allow_legacy_signature: bool = False,
    ) -> ErasureCertificateResponse:
        """Verify HMAC-SHA256 signature, enforce timestamp skew, prevent replay, then cascade erasure."""
        # --- 1. Require secret configured ---
        if not webhook_secret:
            raise AppError(503, "Consent Manager webhook is not configured")

        # --- 2. Parse JSON body ---
        import json
        try:
            body_json = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            raise AppError(400, "Webhook payload is not valid JSON")

        # --- 3. Verify HMAC-SHA256 signature ---
        # Primary, tamper-proof path: raw-body HMAC-SHA256 transmitted in standard signature headers.
        raw_sig = ""
        if signature_header:
            raw_sig = signature_header.strip().lower()
            if raw_sig.startswith("sha256="):
                raw_sig = raw_sig[7:].strip()

        verified = False
        if raw_sig:
            expected_sig = hmac.new(
                webhook_secret.encode(),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            if hmac.compare_digest(expected_sig, raw_sig):
                verified = True

        if not verified:
            # Fallback for legacy Consent Managers sending signature in body or using canonical JSON
            body_sig = (body_json.get("signature") or raw_sig or "").strip().lower()
            if body_sig.startswith("sha256="):
                body_sig = body_sig[7:].strip()

            if body_sig:
                if not allow_legacy_signature:
                    logger.warning(
                        "Rejected legacy Consent Manager signature because allow_legacy_cm_signature is disabled"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Consent manager webhook signature is invalid",
                    )
                request_obj = ConsentWebhookRequest.model_validate(body_json)
                canonical = canonical_cm_webhook(
                    event_id=request_obj.event_id or "",
                    event_type=request_obj.event_type or "",
                    artifact_id=request_obj.effective_artifact_id,
                    farmer_id=request_obj.farmer_id,
                    timestamp=request_obj.timestamp,
                )
                if signature_matches(canonical, body_sig, webhook_secret):
                    verified = True
                    logger.warning(
                        "Webhook signature verified via legacy canonical fallback for artifact=%s",
                        request_obj.effective_artifact_id,
                    )

        if not verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Consent manager webhook signature is invalid",
            )

        # --- 4. Parse and validate timestamp skew ---
        request_obj = ConsentWebhookRequest.model_validate(body_json)
        now_utc = datetime.now(UTC)
        ts = request_obj.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        skew = abs((now_utc - ts).total_seconds())
        if skew > _MAX_SKEW_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Webhook timestamp skew {skew:.0f}s exceeds maximum {_MAX_SKEW_SECONDS}s",
            )

        # --- 5. Redis replay protection ---
        effective_delivery_id = delivery_id or request_obj.effective_delivery_id
        if effective_delivery_id and cache_client:
            replay_key = f"cm_webhook:delivery:{effective_delivery_id}"
            already_seen = await cache_client.get(replay_key)  # type: ignore[attr-defined]
            if already_seen:
                logger.info(
                    "Webhook delivery_id=%s already processed — returning idempotent 200",
                    effective_delivery_id,
                )
                artifact = await self.repository.get(request_obj.effective_artifact_id)
                if artifact is None:
                    raise AppError(404, "Consent artifact not found")
                return ErasureCertificateResponse(
                    certificate_id="REPLAY-IDEMPOTENT",
                    farmer_id=mask_farmer_id(artifact.farmer_id),
                    artifact_id=artifact.artifact_id,
                    status=artifact.status.upper(),
                    reason="Replay: delivery already processed",
                    parcels_purged=0,
                    lots_withdrawn=0,
                    withdrawn_lot_codes=[],
                    cache_keys_evicted=[],
                    verification_hash="",
                    timestamp=now_utc,
                )

        # --- 6. Fetch consent artifact ---
        artifact = await self.repository.get(request_obj.effective_artifact_id)
        if artifact is None:
            raise AppError(404, "Consent artifact not found")

        if artifact.farmer_id != request_obj.farmer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="farmer_id does not match consent artifact",
            )

        # --- 7. Idempotent: already withdrawn ---
        if artifact.status == "withdrawn":
            logger.info(
                "Consent artifact %s already withdrawn — idempotent webhook response",
                artifact.artifact_id,
            )
            return ErasureCertificateResponse(
                certificate_id="ALREADY-WITHDRAWN",
                farmer_id=mask_farmer_id(artifact.farmer_id),
                artifact_id=artifact.artifact_id,
                status="WITHDRAWN",
                reason="Consent was already withdrawn prior to this webhook",
                parcels_purged=0,
                lots_withdrawn=0,
                withdrawn_lot_codes=[],
                cache_keys_evicted=[],
                verification_hash="",
                timestamp=now_utc,
            )

        # --- 8. Execute cascade ---
        engine = AnonymizationEngine(self.session, webhook_secret)
        cert = await engine.execute_cascaded_anonymization(
            artifact,
            reason=request_obj.reason or f"Consent Manager webhook: {request_obj.event_type or 'CONSENT_REVOKED'}",
            event_source=f"cm_webhook:{effective_delivery_id or 'unknown'}",
        )

        # --- 9. Mark delivery seen in Redis (async, best-effort) ---
        if effective_delivery_id and cache_client:
            try:
                await cache_client.setex(replay_key, _REPLAY_TTL_SECONDS, "1")  # type: ignore[attr-defined]
            except Exception:
                pass

        # --- 10. Prometheus counter ---
        try:
            from app.telemetry.metrics import track_consent_revocation
            track_consent_revocation(action="cm_webhook")
        except Exception:
            pass

        return cert

    async def handle_webhook(self, request: ConsentWebhookRequest) -> ErasureCertificateResponse:
        """Legacy JSON-parsed webhook path (preserved for backward compat; does NOT do raw HMAC)."""
        self._require_secret()
        canonical = canonical_cm_webhook(
            event_id=request.event_id or "",
            event_type=request.event_type or "",
            artifact_id=request.effective_artifact_id,
            farmer_id=request.farmer_id,
            timestamp=request.timestamp,
        )
        if not signature_matches(canonical, request.signature or "", self.secret):
            raise AppError(401, "Consent manager webhook signature is invalid")

        artifact = await self.repository.get(request.effective_artifact_id)
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


@router.post(
    "",
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles("farmer", "fpo_operator", "admin", "regulator")),
        Depends(require_org_access("fpo_id")),
    ],
)
async def grant_consent(body: ConsentGrantRequest, service: ConsentServiceDep) -> ConsentResponse:
    return await service.grant(body)


@router.post("/webhook")
async def consent_webhook(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> ErasureCertificateResponse:
    """Inbound Consent Manager revocation webhook. Verifies HMAC-SHA256, enforces timestamp
    skew <5 min, prevents replay via Redis, and cascades erasure.
    """
    raw_body = await request.body()
    # Extract delivery_id and signature from headers if provided
    delivery_id = (
        request.headers.get("x-delivery-id")
        or request.headers.get("x-event-id")
        or None
    )
    signature_header = (
        request.headers.get("x-signature-256")
        or request.headers.get("x-hub-signature-256")
        or request.headers.get("x-consent-signature")
        or None
    )
    # Get cache client for replay prevention (best-effort)
    cache_client = None
    try:
        from app.cache.client import get_cache_client
        cache_client = get_cache_client()
    except Exception:
        pass

    svc = ConsentService(ConsentRepository(session), session, settings.consent_signing_secret)
    return await svc.process_cm_webhook(
        raw_body=raw_body,
        delivery_id=delivery_id,
        signature_header=signature_header,
        webhook_secret=settings.consent_manager_webhook_secret or settings.consent_signing_secret,
        cache_client=cache_client,
        allow_legacy_signature=settings.allow_legacy_cm_signature,
    )


@router.post(
    "/{artifact_id}/withdrawals",
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles("farmer", "fpo_operator", "admin", "regulator")),
        Depends(require_org_access("fpo_id")),
    ],
)
async def withdraw_consent(
    artifact_id: str,
    body: ConsentWithdrawalRequest,
    service: ConsentServiceDep,
) -> ConsentResponse:
    return await service.withdraw(artifact_id, body)


@router.post(
    "/{artifact_id}/anonymize",
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles("farmer", "fpo_operator", "admin", "regulator")),
        Depends(require_org_access("fpo_id")),
    ],
)
async def trigger_anonymization(
    artifact_id: str,
    service: ConsentServiceDep,
) -> ErasureCertificateResponse:
    return await service.anonymize(artifact_id)


@router.get(
    "/{artifact_id}",
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles("farmer", "fpo_operator", "admin", "regulator")),
        Depends(require_org_access("fpo_id")),
    ],
)
async def read_consent(artifact_id: str, service: ConsentServiceDep) -> ConsentResponse:
    return await service.read(artifact_id)


@router.get(
    "/{artifact_id}/audit",
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles("farmer", "fpo_operator", "admin", "regulator")),
        Depends(require_org_access("fpo_id")),
    ],
)
async def audit_consent(
    artifact_id: str,
    service: ConsentServiceDep,
) -> ConsentAuditResponse:
    return await service.audit(artifact_id)


root_consent_router = APIRouter(tags=["consents"])


@root_consent_router.post("/consents/webhook")
async def root_consent_webhook(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> ErasureCertificateResponse:
    """Alias for POST /api/v1/consents/webhook — identical raw-HMAC validation path."""
    raw_body = await request.body()
    delivery_id = (
        request.headers.get("x-delivery-id")
        or request.headers.get("x-event-id")
        or None
    )
    signature_header = (
        request.headers.get("x-signature-256")
        or request.headers.get("x-hub-signature-256")
        or request.headers.get("x-consent-signature")
        or None
    )
    cache_client = None
    try:
        from app.cache.client import get_cache_client
        cache_client = get_cache_client()
    except Exception:
        pass

    svc = ConsentService(ConsentRepository(session), session, settings.consent_signing_secret)
    return await svc.process_cm_webhook(
        raw_body=raw_body,
        delivery_id=delivery_id,
        signature_header=signature_header,
        webhook_secret=settings.consent_manager_webhook_secret or settings.consent_signing_secret,
        cache_client=cache_client,
        allow_legacy_signature=settings.allow_legacy_cm_signature,
    )
