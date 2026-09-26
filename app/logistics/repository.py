from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logistics.models import Facility
from app.logistics.routing import haversine_distance_km
from app.logistics.schemas import FacilityCreateRequest, FacilityPoint


class FacilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_facility(self, request: FacilityCreateRequest) -> FacilityPoint:
        facility = Facility(
            name=request.name,
            facility_type=request.facility_type,
            wdra_registration_no=request.wdra_registration_no,
            state=request.state,
            district=request.district,
            pincode=request.pincode,
            latitude=Decimal(str(request.latitude)),
            longitude=Decimal(str(request.longitude)),
            capacity_quintals=Decimal(str(request.capacity_quintals)),
            available_quintals=Decimal(str(request.available_quintals)),
            cold_storage=request.cold_storage,
            daily_charge_inr_per_quintal=Decimal(str(request.daily_charge_inr_per_quintal)),
        )
        self.session.add(facility)
        await self.session.flush()
        return self._to_point(facility)

    async def list_facilities(
        self,
        *,
        facility_type: str | None = None,
        state: str | None = None,
        district: str | None = None,
        limit: int = 100,
    ) -> list[FacilityPoint]:
        stmt = select(Facility)
        if facility_type:
            stmt = stmt.where(Facility.facility_type == facility_type.upper())
        if state:
            stmt = stmt.where(Facility.state == state)
        if district:
            stmt = stmt.where(Facility.district == district)
        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return [self._to_point(row) for row in result.scalars().all()]

    async def find_nearby_facilities(
        self,
        lat: float,
        lon: float,
        max_radius_km: float = 100.0,
    ) -> list[FacilityPoint]:
        # Fetch facilities and filter by distance using Haversine
        stmt = select(Facility)
        result = await self.session.execute(stmt)
        facilities = result.scalars().all()

        points: list[FacilityPoint] = []
        for fac in facilities:
            dist = haversine_distance_km(lat, lon, float(fac.latitude), float(fac.longitude))
            if dist <= max_radius_km:
                pt = self._to_point(fac)
                pt.distance_km = dist
                points.append(pt)

        points.sort(key=lambda p: p.distance_km or 0.0)
        return points

    def _to_point(self, f: Facility) -> FacilityPoint:
        return FacilityPoint(
            id=f.id,
            name=f.name,
            facility_type=f.facility_type,
            wdra_registration_no=f.wdra_registration_no,
            state=f.state,
            district=f.district,
            pincode=f.pincode,
            latitude=float(f.latitude),
            longitude=float(f.longitude),
            capacity_quintals=float(f.capacity_quintals),
            available_quintals=float(f.available_quintals),
            cold_storage=f.cold_storage,
            daily_charge_inr_per_quintal=float(f.daily_charge_inr_per_quintal),
        )
