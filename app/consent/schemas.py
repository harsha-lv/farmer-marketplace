from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ConsentGrantRequest(BaseModel):
    artifact_id: str = Field(pattern=r"^[A-Za-z0-9-]{6,128}$")
    farmer_id: str = Field(pattern=r"^[A-Za-z0-9-]{6,64}$")
    purpose: str = Field(min_length=1, max_length=160)
    attributes: list[str] = Field(min_length=1)
    created_at: datetime
    expires_at: datetime
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("created_at", "expires_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @field_validator("attributes")
    @classmethod
    def attributes_are_tokens(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            token = item.strip()
            if not token or len(token) > 64:
                raise ValueError("attribute names must be 1 to 64 characters")
            cleaned.append(token)
        return cleaned


class ConsentWithdrawalRequest(BaseModel):
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")


class ConsentResponse(BaseModel):
    artifact_id: str
    farmer_id: str
    purpose: str
    attributes: list[str]
    created_at: datetime
    expires_at: datetime
    status: str
    withdrawn_at: datetime | None
