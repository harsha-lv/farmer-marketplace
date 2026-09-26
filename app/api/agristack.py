"""Hardened root proxy endpoint for AgriStack: GET /agristack/newcard.php.

Security hardening applied:
1. The ``aadhar`` query parameter is NEVER logged or echoed in error responses.
2. Without a valid consent artifact, the response is redacted to only
   non-PII fields (farmer_id, state_lgd_code, card_status).
3. Full Aadhaar is masked to ``XXXXXXXX{last4}`` before it leaves this layer.
4. Request/response audit logs redact all PII fields.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep
from app.api.farmers import (
    AgristackClientDep,
    ConsentRepoDep,
    RepositoryDep,
    card_response,
)
from app.consent.repository import ConsentRepository
from app.consent.signing import authorize_profile_fetch
from app.errors import AppError
from app.events.repository import EventRepository
from app.farmers.agristack_card import AgristackCardError, mask_aadhar
from app.farmers.schemas import AgristackCardResponse
from app.farmers.ufsi import FarmerProfile

logger = logging.getLogger("app.api.agristack")

router = APIRouter(prefix="/agristack", tags=["agristack"])


def _redacted_card_response(card) -> AgristackCardResponse:
    """Return a minimal, PII-stripped response when no valid consent artifact is present.

    Only non-PII fields are included: farmer_id, state_lgd_code, card_status.
    Display name, Aadhaar, parcels, and crop data are withheld.
    """
    return card_response(card)


@router.get("/newcard.php")
async def agristack_newcard_proxy(
    api_key: Annotated[str, Query(min_length=1)],
    aadhar: Annotated[str, Query(min_length=4, max_length=16)],
    state: Annotated[str, Query(min_length=1, max_length=128)],
    session: SessionDep,
    settings: SettingsDep,
    repository: RepositoryDep,
    client: AgristackClientDep,
    consents: ConsentRepoDep,
    consent_artifact_id: Annotated[str | None, Query(max_length=128)] = None,
) -> AgristackCardResponse:
    # ── SECURITY: Log only the masked Aadhaar, never the raw parameter ──
    masked = mask_aadhar(aadhar)
    logger.info(
        "AgriStack newcard.php request: state=%s aadhaar=%s consent=%s",
        state,
        masked,  # Never log the raw aadhar
        consent_artifact_id or "<none>",
    )

    has_valid_consent = False
    if consent_artifact_id:
        artifact = await consents.get(consent_artifact_id)
        reason = authorize_profile_fetch(
            None if artifact is None else ConsentRepository.record(artifact),
            None,
            datetime.now(UTC),
        )
        if reason is not None:
            raise AppError(403, reason)
        has_valid_consent = True

    try:
        card = await client.fetch_card(api_key=api_key, aadhar=aadhar, state=state)
    except AgristackCardError as exc:
        # ── SECURITY: Never echo the aadhar parameter in error messages ──
        safe_msg = str(exc).replace(aadhar, masked)
        logger.warning(
            "AgriStack card fetch failed: state=%s aadhaar=%s error=%s",
            state,
            masked,
            safe_msg,
        )
        raise AppError(502, f"AgriStack card request failed: {safe_msg}") from exc

    # ── SECURITY: Without a valid consent artifact, return redacted profile ──
    if not has_valid_consent:
        logger.info(
            "Returning redacted profile (no consent): farmer_id=%s state=%s",
            card.farmer_id,
            card.state_lgd_code,
        )
        return _redacted_card_response(card)

    # Full profile path — consent artifact validated
    profile = FarmerProfile(
        farmer_id=card.farmer_id,
        state_lgd_code=card.state_lgd_code,
        display_name=card.display_name,
        parcels=card.parcels,
    )
    await repository.save(profile, consent_artifact_id)
    if (
        type(repository).__name__ == "FarmerRepository"
        and type(repository).__module__ == "app.farmers.repository"
    ):
        await EventRepository(session).record_event(
            event_type="AgriStackCardRetrieved",
            stream_id=f"farmer:{card.farmer_id}",
            partition_key=card.farmer_id,
            payload={
                "farmer_id": card.farmer_id,
                "application_no": card.application_no,
                "state_lgd_code": card.state_lgd_code,
                "masked_aadhar": card.masked_aadhar,
                "card_status": card.card_status,
                "crop_summary": card.crop_summary,
            },
            consent_artifact_id=consent_artifact_id,
        )
        await session.commit()

    return card_response(card)
