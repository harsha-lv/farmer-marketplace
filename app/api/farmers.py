from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, SettingsDep
from app.errors import AppError
from app.farmers.models import Farmer
from app.farmers.repository import FarmerRepository
from app.farmers.schemas import (
    CropResponse,
    FarmerProfileRequest,
    FarmerProfileResponse,
    ParcelResponse,
)
from app.farmers.ufsi import RegistryError, UfsiClient

router = APIRouter(prefix="/farmers", tags=["farmers"])


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
    def __init__(self, client: UfsiClient, repository: FarmerRepository, session: AsyncSession) -> None:
        self.client = client
        self.repository = repository
        self.session = session

    async def resolve(self, request: FarmerProfileRequest) -> FarmerProfileResponse:
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
