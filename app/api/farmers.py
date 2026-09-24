from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, SettingsDep
from app.consent.repository import ConsentRepository
from app.consent.signing import authorize_profile_fetch
from app.errors import AppError
from app.events.repository import EventRepository
from app.farmers.agristack_card import AgristackCardClient, AgristackCardData, AgristackCardError
from app.farmers.models import Farmer
from app.farmers.repository import FarmerRepository
from app.farmers.schemas import (
    AgristackCardRequest,
    AgristackCardResponse,
    CropResponse,
    CropSownVerificationRequest,
    CropSownVerificationResponse,
    FarmerProfileRequest,
    FarmerProfileResponse,
    ParcelResponse,
)
from app.farmers.ufsi import FarmerProfile, RegistryError, UfsiClient
from app.farmers.verification import verify_crop_cultivation

router = APIRouter(prefix="/farmers", tags=["farmers"])


def card_response(card: AgristackCardData) -> AgristackCardResponse:
    return AgristackCardResponse(
        farmer_id=card.farmer_id,
        application_no=card.application_no,
        state_lgd_code=card.state_lgd_code,
        state_name=card.state_name,
        district_name=card.district_name,
        display_name=card.display_name,
        masked_aadhar=card.masked_aadhar,
        gender=card.gender,
        dob_or_age=card.dob_or_age,
        card_status=card.card_status,
        pdf_download_url=card.pdf_download_url,
        qr_code_payload=card.qr_code_payload,
        parcels=[
            ParcelResponse(
                farm_id=p.farm_id,
                area_hectares=p.area_hectares,
                crops=[CropResponse(commodity=c.commodity, season=c.season) for c in p.crops],
            )
            for p in card.parcels
        ],
        crop_summary=card.crop_summary,
        fetched_at=card.fetched_at,
    )


def profile_response(farmer: Farmer) -> FarmerProfileResponse:
    return FarmerProfileResponse(
        farmer_id=farmer.farmer_id,
        state_lgd_code=farmer.state_lgd_code,
        display_name=farmer.display_name,
        consent_artifact_id=farmer.consent_artifact_id,
        fetched_at=farmer.fetched_at,
        parcels=[
            ParcelResponse(
                farm_id=parcel.farm_id,
                area_hectares=parcel.area_hectares,
                crops=[
                    CropResponse(commodity=crop.commodity, season=crop.season) for crop in parcel.crops
                ],
            )
            for parcel in farmer.parcels
        ],
    )


class ProfileResolver:
    def __init__(
        self,
        client: UfsiClient,
        repository: FarmerRepository,
        consents: ConsentRepository,
        session: AsyncSession,
    ) -> None:
        self.client = client
        self.repository = repository
        self.consents = consents
        self.session = session

    async def resolve(self, request: FarmerProfileRequest) -> FarmerProfileResponse:
        artifact = await self.consents.get(request.consent_artifact_id)
        reason = authorize_profile_fetch(
            None if artifact is None else ConsentRepository.record(artifact),
            request.farmer_id,
            datetime.now(UTC),
        )
        if reason is not None:
            raise AppError(403, reason)
        profile = await self.client.fetch_profile(
            farmer_id=request.farmer_id,
            state_lgd_code=request.state_lgd_code,
            consent_artifact_id=request.consent_artifact_id,
        )
        farmer = await self.repository.save(profile, request.consent_artifact_id)
        await self.session.commit()
        return profile_response(farmer)


def get_farmer_repository(session: SessionDep) -> FarmerRepository:
    return FarmerRepository(session)


def get_resolver(session: SessionDep, settings: SettingsDep) -> ProfileResolver:
    if not settings.ufsi_base_url:
        raise AppError(503, "Farmer registry is not configured")
    return ProfileResolver(
        UfsiClient(settings.ufsi_base_url),
        FarmerRepository(session),
        ConsentRepository(session),
        session,
    )


RepositoryDep = Annotated[FarmerRepository, Depends(get_farmer_repository)]
ResolverDep = Annotated[ProfileResolver, Depends(get_resolver)]


@router.post("/profile")
async def resolve_farmer(body: FarmerProfileRequest, resolver: ResolverDep) -> FarmerProfileResponse:
    try:
        return await resolver.resolve(body)
    except RegistryError as exc:
        raise AppError(502, "Farmer registry request failed") from exc


@router.get("/{farmer_id}")
async def read_farmer(farmer_id: str, repository: RepositoryDep) -> FarmerProfileResponse:
    farmer = await repository.get(farmer_id)
    if farmer is None:
        raise AppError(404, "Farmer not found")
    return profile_response(farmer)


def get_agristack_client(settings: SettingsDep) -> AgristackCardClient:
    base_url = settings.agristack_base_url or settings.ufsi_base_url
    if not base_url:
        raise AppError(503, "AgriStack service is not configured")
    return AgristackCardClient(base_url)


def get_consent_repository(session: SessionDep) -> ConsentRepository:
    return ConsentRepository(session)


AgristackClientDep = Annotated[AgristackCardClient, Depends(get_agristack_client)]
ConsentRepoDep = Annotated[ConsentRepository, Depends(get_consent_repository)]


async def _handle_card_resolution(
    *,
    api_key: str,
    aadhar: str,
    state: str,
    consent_artifact_id: str | None,
    client: AgristackCardClient,
    repository: FarmerRepository,
    consents: ConsentRepository,
    session: AsyncSession,
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


@router.post("/card")
async def resolve_card_post(
    body: AgristackCardRequest,
    client: AgristackClientDep,
    repository: RepositoryDep,
    consents: ConsentRepoDep,
    session: SessionDep,
) -> AgristackCardResponse:
    return await _handle_card_resolution(
        api_key=body.api_key,
        aadhar=body.aadhar,
        state=body.state,
        consent_artifact_id=body.consent_artifact_id,
        client=client,
        repository=repository,
        consents=consents,
        session=session,
    )


@router.get("/card")
async def resolve_card_get(
    client: AgristackClientDep,
    repository: RepositoryDep,
    consents: ConsentRepoDep,
    session: SessionDep,
    api_key: Annotated[str, Query(min_length=1)],
    aadhar: Annotated[str, Query(min_length=4, max_length=16)],
    state: Annotated[str, Query(min_length=1, max_length=128)],
    consent_artifact_id: Annotated[str | None, Query(max_length=128)] = None,
) -> AgristackCardResponse:
    return await _handle_card_resolution(
        api_key=api_key,
        aadhar=aadhar,
        state=state,
        consent_artifact_id=consent_artifact_id,
        client=client,
        repository=repository,
        consents=consents,
        session=session,
    )


@router.post("/verify-cultivation")
async def verify_farmer_cultivation(
    body: CropSownVerificationRequest,
    repository: RepositoryDep,
    consents: ConsentRepoDep,
    session: SessionDep,
    settings: SettingsDep,
) -> CropSownVerificationResponse:
    farmer = await repository.get(body.farmer_id)
    if farmer is None:
        raise AppError(404, "Farmer not found")

    artifact = await consents.get(body.consent_artifact_id)
    reason = authorize_profile_fetch(
        None if artifact is None else ConsentRepository.record(artifact),
        body.farmer_id,
        datetime.now(UTC),
    )
    if reason is not None:
        raise AppError(403, reason)

    secret = settings.consent_signing_secret or "agristack-verification-secret"
    result = verify_crop_cultivation(
        farmer,
        commodity=body.commodity,
        season=body.season,
        claimed_quantity_mt=body.claimed_quantity_mt,
        secret_key=secret,
    )

    if (
        type(repository).__name__ == "FarmerRepository"
        and type(repository).__module__ == "app.farmers.repository"
    ):
        await EventRepository(session).record_event(
            event_type="CropSownVerified",
            stream_id=f"farmer:{farmer.farmer_id}",
            partition_key=farmer.farmer_id,
            payload={
                "farmer_id": result.farmer_id,
                "commodity": result.commodity,
                "is_cultivation_verified": result.is_cultivation_verified,
                "verification_status": result.verification_status,
                "matched_parcels": result.matched_parcels,
                "total_cultivated_area_hectares": str(result.total_cultivated_area_hectares),
                "estimated_max_yield_mt": str(result.estimated_max_yield_mt),
                "authenticity_certificate": result.authenticity_certificate,
            },
            consent_artifact_id=body.consent_artifact_id,
        )
        await session.commit()

    return CropSownVerificationResponse(
        farmer_id=result.farmer_id,
        commodity=result.commodity,
        is_cultivation_verified=result.is_cultivation_verified,
        verification_status=result.verification_status,
        matched_parcels=result.matched_parcels,
        total_cultivated_area_hectares=result.total_cultivated_area_hectares,
        estimated_max_yield_mt=result.estimated_max_yield_mt,
        authenticity_certificate=result.authenticity_certificate,
        survey_season=result.survey_season,
        rationale=result.rationale,
    )
