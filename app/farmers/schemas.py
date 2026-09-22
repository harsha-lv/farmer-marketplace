from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.prices.lgd import canonical_state_lgd_code


class FarmerProfileRequest(BaseModel):
    farmer_id: str = Field(pattern=r"^[A-Za-z0-9-]{6,64}$")
    state_lgd_code: str = Field(min_length=1, max_length=2)
    consent_artifact_id: str = Field(min_length=1, max_length=128)

    @field_validator("state_lgd_code")
    @classmethod
    def known_state(cls, value: str) -> str:
        canonical = canonical_state_lgd_code(value)
        if canonical is None:
            raise ValueError("unknown state code")
        return canonical


class CropResponse(BaseModel):
    commodity: str
    season: str


class ParcelResponse(BaseModel):
    farm_id: str
    area_hectares: Decimal | None
    crops: list[CropResponse]


class FarmerProfileResponse(BaseModel):
    farmer_id: str
    state_lgd_code: str
    display_name: str
    consent_artifact_id: str
    fetched_at: datetime
    parcels: list[ParcelResponse]
