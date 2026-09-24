"""Direct root proxy endpoint for AgriStack: GET /agristack/newcard.php."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, SettingsDep
from app.api.farmers import AgristackClientDep, ConsentRepoDep, RepositoryDep, card_response
from app.consent.repository import ConsentRepository
from app.consent.signing import authorize_profile_fetch
from app.errors import AppError
from app.events.repository import EventRepository
from app.farmers.agristack_card import AgristackCardError
from app.farmers.schemas import AgristackCardResponse
from app.farmers.ufsi import FarmerProfile

router = APIRouter(prefix="/agristack", tags=["agristack"])


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
    if consent_artifact_id:
        artifact = await consents.get(consent_artifact_id)
        reason = authorize_profile_fetch(
            None if artifact is None else ConsentRepository.record(artifact),
            None,
            datetime.now(UTC),
        )
        if reason is not None:
            raise AppError(403, reason)

    try:
        card = await client.fetch_card(api_key=api_key, aadhar=aadhar, state=state)
    except AgristackCardError as exc:
        raise AppError(502, f"AgriStack card request failed: {exc}") from exc

    if consent_artifact_id:
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
