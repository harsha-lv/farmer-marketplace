from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.farmers.models import CropRecord, Farmer, LandParcel
from app.farmers.ufsi import FarmerProfile


class FarmerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, farmer_id: str) -> Farmer | None:
        statement = (
            select(Farmer)
            .where(Farmer.farmer_id == farmer_id)
            .options(selectinload(Farmer.parcels).selectinload(LandParcel.crops))
        )
        return await self.session.scalar(statement)

    async def save(self, profile: FarmerProfile, consent_artifact_id: str) -> Farmer:
        farmer = await self.get(profile.farmer_id)
        if farmer is None:
            farmer = Farmer(
                farmer_id=profile.farmer_id,
                state_lgd_code=profile.state_lgd_code,
                display_name=profile.display_name,
                consent_artifact_id=consent_artifact_id,
                fetched_at=datetime.now(UTC),
            )
            self.session.add(farmer)
            await self.session.flush()
        else:
            farmer.state_lgd_code = profile.state_lgd_code
            farmer.display_name = profile.display_name
            farmer.consent_artifact_id = consent_artifact_id
            farmer.fetched_at = datetime.now(UTC)
            parcel_ids = select(LandParcel.id).where(LandParcel.farmer_id == farmer.id)
            await self.session.execute(delete(CropRecord).where(CropRecord.parcel_id.in_(parcel_ids)))
            await self.session.execute(delete(LandParcel).where(LandParcel.farmer_id == farmer.id))
            await self.session.flush()
        await self.session.refresh(farmer, attribute_names=["parcels"])
        for holding in profile.parcels:
            parcel = LandParcel(farm_id=holding.farm_id, area_hectares=holding.area_hectares)
            parcel.crops = [
                CropRecord(commodity=crop.commodity, season=crop.season) for crop in holding.crops
            ]
            farmer.parcels.append(parcel)
        await self.session.flush()
        return farmer
