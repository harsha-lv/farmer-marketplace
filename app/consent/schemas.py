from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class ConsentWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    event_id: str | None = None
    delivery_id: str | None = None
    event_type: str | None = None
    action: str | None = None
    artifact_id: str | None = None
    consent_id: str | None = None
    farmer_id: str
    purpose: str | None = None
    timestamp: datetime
    reason: str | None = None
    signature: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "artifact_id" not in data and "consent_id" in data:
                data["artifact_id"] = data["consent_id"]
            elif "consent_id" not in data and "artifact_id" in data:
                data["consent_id"] = data["artifact_id"]
            
            if "event_id" not in data and "delivery_id" in data:
                data["event_id"] = data["delivery_id"]
            elif "delivery_id" not in data and "event_id" in data:
                data["delivery_id"] = data["event_id"]

            if "event_type" not in data and "action" in data:
                act = str(data["action"]).upper()
                if "REVOK" in act:
                    data["event_type"] = "CONSENT_REVOKED"
                else:
                    data["event_type"] = act
            elif "action" not in data and "event_type" in data:
                data["action"] = data["event_type"]
        return data

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_and_validate_timestamp(cls, value: Any) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    @property
    def effective_artifact_id(self) -> str:
        return self.artifact_id or self.consent_id or ""

    @property
    def effective_delivery_id(self) -> str:
        return self.delivery_id or self.event_id or ""


class ErasureCertificateResponse(BaseModel):
    certificate_id: str
    farmer_id: str
    artifact_id: str
    status: str
    reason: str
    parcels_purged: int
    lots_withdrawn: int
    withdrawn_lot_codes: list[str]
    cache_keys_evicted: list[str]
    verification_hash: str
    timestamp: datetime


class ConsentAuditResponse(BaseModel):
    artifact_id: str
    farmer_id: str
    purpose: str
    attributes: list[str]
    created_at: datetime
    expires_at: datetime
    status: str
    withdrawn_at: datetime | None
    erasure_certificate: ErasureCertificateResponse | None
    audit_events: list[dict]
