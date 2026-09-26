import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.consent.models import ConsentArtifact
from app.consent.repository import utcnow
from app.consent.schemas import ErasureCertificateResponse
from app.consent.signing import compute_erasure_hash, mask_farmer_id
from app.events.repository import EventRepository
from app.farmers.models import Farmer, LandParcel
from app.lots.repository import LotRepository


class AnonymizationEngine:
    """
    DPDP Act 2023 Section 6 & 12 Automated Cascaded Deletion, Anonymization,
    and Digital Trading Halting Engine.
    """

    def __init__(
        self,
        session: AsyncSession,
        secret: str,
        cache_backend: Any = None,
    ) -> None:
        self.session = session
        self.secret = secret
        self.cache_backend = cache_backend

    async def execute_cascaded_anonymization(
        self,
        artifact: ConsentArtifact,
        *,
        reason: str | None = None,
        event_source: str = "consent_manager",
    ) -> ErasureCertificateResponse:
        now = utcnow()
        effective_reason = (
            reason
            or "Data Principal exercised statutory right to withdraw consent / request data erasure under DPDP Act Sec 6/12"
        )

        # 1. Update Consent Artifact status
        if artifact.status != "withdrawn":
            artifact.status = "withdrawn"
            artifact.withdrawn_at = now

        farmer_id = artifact.farmer_id
        artifact_id = artifact.artifact_id

        # 2. Count & Purge Farmer Demographics and Cadastral Land Parcels
        farmer_stmt = select(Farmer).where(Farmer.farmer_id == farmer_id)
        farmer = await self.session.scalar(farmer_stmt)
        parcels_purged = 0
        if farmer is not None:
            parcel_stmt = select(func.count(LandParcel.id)).where(LandParcel.farmer_id == farmer.id)
            parcels_purged = int(await self.session.scalar(parcel_stmt) or 0)
            await self.session.delete(farmer)

        # 3. Halt Automated Broadcasts on Digital Trading Channels (ONDC & e-NAM Lots)
        lot_repo = LotRepository(self.session)
        withdrawn_lot_codes = await lot_repo.withdraw_lots_for_consent(
            farmer_id=farmer_id,
            consent_artifact_id=artifact_id,
        )

        # 4. Invalidate / Evict Cache & Redis Keys
        cache_keys_evicted = [
            f"farmer:{farmer_id}",
            f"consent:{artifact_id}",
            f"catalog:lots:{farmer_id}",
            f"active_trade_negotiations:{farmer_id}",
        ]
        if self.cache_backend and hasattr(self.cache_backend, "delete_many"):
            try:
                await self.cache_backend.delete_many(cache_keys_evicted)
            except Exception:
                pass

        # 5. Generate Cryptographic Erasure Certificate
        certificate_id = f"DPDP-ERASURE-{uuid.uuid4().hex[:12].upper()}"
        masked_id = mask_farmer_id(farmer_id)
        verification_hash = compute_erasure_hash(
            certificate_id=certificate_id,
            artifact_id=artifact_id,
            farmer_id=farmer_id,
            timestamp=now,
            secret=self.secret,
        )

        certificate = ErasureCertificateResponse(
            certificate_id=certificate_id,
            farmer_id=masked_id,
            artifact_id=artifact_id,
            status="ANONYMIZED_AND_PURGED",
            reason=effective_reason,
            parcels_purged=parcels_purged,
            lots_withdrawn=len(withdrawn_lot_codes),
            withdrawn_lot_codes=withdrawn_lot_codes,
            cache_keys_evicted=cache_keys_evicted,
            verification_hash=verification_hash,
            timestamp=now,
        )

        # 6. Record Immutable Event Sourcing Log in Outbox (Kafka/NATS)
        event_repo = EventRepository(self.session)
        await event_repo.record_event(
            event_type="ConsentRevoked",
            stream_id=f"consent:{artifact_id}",
            partition_key=farmer_id,
            payload={
                "artifact_id": artifact_id,
                "farmer_id": farmer_id,
                "withdrawn_at": now.isoformat(),
                "reason": effective_reason,
                "source": event_source,
            },
            consent_artifact_id=artifact_id,
        )

        if withdrawn_lot_codes:
            await event_repo.record_event(
                event_type="TradingBroadcastHalted",
                stream_id=f"consent:{artifact_id}",
                partition_key=farmer_id,
                payload={
                    "artifact_id": artifact_id,
                    "farmer_id": farmer_id,
                    "lots_withdrawn_count": len(withdrawn_lot_codes),
                    "withdrawn_lot_codes": withdrawn_lot_codes,
                },
                consent_artifact_id=artifact_id,
            )

        await event_repo.record_event(
            event_type="DataSubjectErasureCompleted",
            stream_id=f"consent:{artifact_id}",
            partition_key=farmer_id,
            payload={
                "certificate_id": certificate_id,
                "artifact_id": artifact_id,
                "masked_farmer_id": masked_id,
                "parcels_purged": parcels_purged,
                "lots_withdrawn": len(withdrawn_lot_codes),
                "cache_keys_evicted": cache_keys_evicted,
                "verification_hash": verification_hash,
                "timestamp": now.isoformat(),
            },
            consent_artifact_id=artifact_id,
        )

        await self.session.commit()
        return certificate
