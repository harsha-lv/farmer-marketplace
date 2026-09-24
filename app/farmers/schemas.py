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


class AgristackCardRequest(BaseModel):
    api_key: str = Field(min_length=1)
    aadhar: str = Field(min_length=4, max_length=16)
    state: str = Field(min_length=1, max_length=128)
    consent_artifact_id: str | None = None


class AgristackCardResponse(BaseModel):
    farmer_id: str
    application_no: str
    state_lgd_code: str
    state_name: str
    district_name: str | None = None
    display_name: str
    masked_aadhar: str
    gender: str | None = None
    dob_or_age: str | None = None
    card_status: str
    pdf_download_url: str | None = None
    qr_code_payload: str
    parcels: list[ParcelResponse]
    crop_summary: list[str]
    fetched_at: datetime


class CropSownVerificationRequest(BaseModel):
    farmer_id: str = Field(pattern=r"^[A-Za-z0-9-]{6,64}$")
    commodity: str = Field(min_length=1, max_length=128)
    season: str | None = Field(default=None, max_length=64)
    claimed_quantity_mt: Decimal | None = Field(default=None, ge=Decimal(0))
    consent_artifact_id: str = Field(min_length=1, max_length=128)


class CropSownVerificationResponse(BaseModel):
    farmer_id: str
    commodity: str
    is_cultivation_verified: bool
    verification_status: str
    matched_parcels: list[str]
    total_cultivated_area_hectares: Decimal
    estimated_max_yield_mt: Decimal
    authenticity_certificate: str
    survey_season: str
    rationale: str
