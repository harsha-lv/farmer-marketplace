from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep
from app.errors import AppError
from app.logistics.repository import FacilityRepository
from app.logistics.routing import calculate_freight_quote, rank_and_allocate_facilities
from app.logistics.schemas import (
    FacilityAllocationRequest,
    FacilityAllocationResponse,
    FacilityCreateRequest,
    FacilityPoint,
    RouteCalculationRequest,
    RouteCalculationResponse,
)

router = APIRouter(prefix="/logistics", tags=["logistics"])


def get_facility_repository(session: SessionDep) -> FacilityRepository:
    return FacilityRepository(session)


FacilityRepoDep = Annotated[FacilityRepository, Depends(get_facility_repository)]


@router.post("/route", response_model=RouteCalculationResponse)
async def calculate_route(request: RouteCalculationRequest) -> RouteCalculationResponse:
    """Calculate point-to-point geodesic & road distance, estimated transit time, and freight cost quote."""
    return calculate_freight_quote(request)


@router.post("/allocate", response_model=FacilityAllocationResponse)
async def allocate_facility(
    request: FacilityAllocationRequest,
    repo: FacilityRepoDep,
) -> FacilityAllocationResponse:
    """Find and rank nearest warehouses / mandis and recommend the optimal facility based on storage/liquidation intent."""
    facilities = await repo.find_nearby_facilities(
        lat=request.origin.latitude,
        lon=request.origin.longitude,
        max_radius_km=request.max_radius_km,
    )
    return rank_and_allocate_facilities(facilities, request)


@router.get("/facilities", response_model=list[FacilityPoint])
async def list_facilities(
    repo: FacilityRepoDep,
    facility_type: Annotated[str | None, Query(max_length=32)] = None,
    state: Annotated[str | None, Query(max_length=128)] = None,
    district: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[FacilityPoint]:
    """List registered physical agricultural facilities (warehouses, mandis, cold storage)."""
    return await repo.list_facilities(
        facility_type=facility_type,
        state=state,
        district=district,
        limit=limit,
    )


@router.post("/facilities", response_model=FacilityPoint, status_code=status.HTTP_201_CREATED)
async def create_facility(
    request: FacilityCreateRequest,
    repo: FacilityRepoDep,
) -> FacilityPoint:
    """Register a new warehouse, mandi, or cold storage depot with geo-coordinates."""
    if request.available_quintals > request.capacity_quintals:
        raise AppError(
            422,
            "Invalid request",
            "available_quintals cannot exceed total capacity_quintals",
        )
    return await repo.create_facility(request)
