"""Strict Pydantic v2 schemas for Beckn Protocol v2.0.0 and ONDC:AGR10 agriculture domain.

Includes:
  - JSON-LD @context specification
  - Canonical BecknContext v2.0.0
  - Request and on_* callback schemas for all 10 flows:
    search, select, init, confirm, status, track, cancel, update, support, rating
  - Standardized ACK and NACK Beckn error envelopes
"""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_JSONLD_CONTEXT: dict[str, Any] = {
    "@vocab": "https://becknprotocol.io/schema/v2",
    "ondc": "https://ondc.org/schema/v2",
    "agr": "https://ondc.org/schema/agr/v2",
}

DOMAIN_AGRICULTURE = "ONDC:AGR10"
PROTOCOL_VERSION_V2 = "2.0.0"
PROTOCOL_VERSION_V1 = "1.2.0"


class AckStatus(str, Enum):
    ACK = "ACK"
    NACK = "NACK"


class BecknAck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: AckStatus = AckStatus.ACK


class BecknError(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str
    message: str
    path: str | None = None
    type: str = "DOMAIN-ERROR"


class BecknContext(BaseModel):
    """Canonical Beckn Protocol v2.0.0 context with JSON-LD block."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    json_ld_context: dict[str, Any] | None = Field(default=None, alias="@context")
    domain: str = DOMAIN_AGRICULTURE
    action: str
    version: str = PROTOCOL_VERSION_V2
    core_version: str = PROTOCOL_VERSION_V2
    bap_id: str
    bap_uri: str
    bpp_id: str | None = None
    bpp_uri: str | None = None
    transaction_id: str
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    ttl: str | None = "PT30S"
    location: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_context_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "@context" not in data and "json_ld_context" not in data:
                data["@context"] = DEFAULT_JSONLD_CONTEXT
            if "version" not in data or not data["version"]:
                data["version"] = PROTOCOL_VERSION_V2
            if "core_version" not in data:
                data["core_version"] = data.get("version", PROTOCOL_VERSION_V2)
            if "domain" not in data or not data["domain"]:
                data["domain"] = DOMAIN_AGRICULTURE
            if "timestamp" not in data or not data["timestamp"]:
                data["timestamp"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return data


class BecknResponse(BaseModel):
    """Canonical Beckn ACK / NACK response structure."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    context: dict[str, Any]
    message: dict[str, Any] = Field(default_factory=lambda: {"ack": {"status": "ACK"}})
    error: BecknError | None = None


def build_beckn_ack(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": context,
        "message": {"ack": {"status": "ACK"}},
    }


def build_beckn_nack(
    context: dict[str, Any],
    code: str,
    message: str,
    path: str | None = None,
) -> dict[str, Any]:
    return {
        "context": context,
        "message": {"ack": {"status": "NACK"}},
        "error": {
            "code": str(code),
            "message": str(message),
            "path": path,
            "type": "DOMAIN-ERROR",
        },
    }


# ---------------------------------------------------------------------------
# Flow 1: Search & On_Search
# ---------------------------------------------------------------------------


class SearchIntent(BaseModel):
    model_config = ConfigDict(extra="allow")
    item: dict[str, Any] | None = None
    category: dict[str, Any] | None = None
    fulfillment: dict[str, Any] | None = None
    provider: dict[str, Any] | None = None
    tags: list[dict[str, Any]] | None = None


class SearchMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    intent: SearchIntent | None = None


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: SearchMessage | None = None


class OnSearchMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    catalog: dict[str, Any]


class OnSearchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: OnSearchMessage


# ---------------------------------------------------------------------------
# Flow 2: Select & On_Select
# ---------------------------------------------------------------------------


class SelectItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    quantity: dict[str, Any] | None = None


class SelectOrder(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider: dict[str, Any] | None = None
    items: list[SelectItem]
    fulfillments: list[dict[str, Any]] | None = None


class SelectMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order: SelectOrder


class SelectRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: SelectMessage


class OnSelectMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order: dict[str, Any]


class OnSelectRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: OnSelectMessage


# ---------------------------------------------------------------------------
# Flow 3: Init & On_Init
# ---------------------------------------------------------------------------


class InitBilling(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None


class InitOrder(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider: dict[str, Any] | None = None
    items: list[SelectItem]
    billing: InitBilling
    fulfillments: list[dict[str, Any]] | None = None


class InitMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order: InitOrder


class InitRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: InitMessage


class OnInitMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order: dict[str, Any]


class OnInitRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: OnInitMessage


# ---------------------------------------------------------------------------
# Flow 4: Confirm & On_Confirm
# ---------------------------------------------------------------------------


class ConfirmOrder(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    provider: dict[str, Any] | None = None
    items: list[SelectItem]
    billing: InitBilling | None = None
    fulfillments: list[dict[str, Any]] | None = None
    payment: dict[str, Any] | None = None


class ConfirmMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order: ConfirmOrder


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: ConfirmMessage


class OnConfirmMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order: dict[str, Any]


class OnConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: OnConfirmMessage


# ---------------------------------------------------------------------------
# Flow 5: Status & On_Status
# ---------------------------------------------------------------------------


class StatusMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order_id: str | None = None


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: StatusMessage | None = None


class OnStatusMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order: dict[str, Any]


class OnStatusRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: OnStatusMessage


# ---------------------------------------------------------------------------
# Flow 6: Track & On_Track
# ---------------------------------------------------------------------------


class TrackMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order_id: str | None = None
    callback_url: str | None = None


class TrackRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: TrackMessage | None = None


class OnTrackMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    tracking: dict[str, Any]


class OnTrackRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: OnTrackMessage


# ---------------------------------------------------------------------------
# Flow 7: Cancel & On_Cancel
# ---------------------------------------------------------------------------


class CancelMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order_id: str
    cancellation_reason_id: str | None = None
    descriptor: dict[str, Any] | None = None


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: CancelMessage


class OnCancelMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order: dict[str, Any]


class OnCancelRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: OnCancelMessage


# ---------------------------------------------------------------------------
# Flow 8: Update & On_Update
# ---------------------------------------------------------------------------


class UpdateMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    update_target: str | None = None
    order: dict[str, Any]


class UpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: UpdateMessage


class OnUpdateMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    order: dict[str, Any]


class OnUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: OnUpdateMessage


# ---------------------------------------------------------------------------
# Flow 9: Support & On_Support (IGM Issue Integration)
# ---------------------------------------------------------------------------


class IgmIssue(BaseModel):
    """ONDC IGM Issue Object."""
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    category: str = "QUALITY"
    sub_category: str = "MOISTURE_EXCESS"
    description: str = "Quality parameter discrepancy"
    status: str = "OPEN"
    expected_response_time: str = "PT48H"
    complainant_info: dict[str, Any] | None = None
    respondent_info: dict[str, Any] | None = None


class SupportMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    ref_id: str | None = None
    issue: IgmIssue | None = None


class SupportRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: SupportMessage | None = None


class OnSupportMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    phone: str | None = None
    email: str | None = None
    uri: str | None = None
    issue: IgmIssue | None = None
    tags: list[dict[str, Any]] | None = None


class OnSupportRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: OnSupportMessage


# ---------------------------------------------------------------------------
# Flow 10: Rating & On_Rating
# ---------------------------------------------------------------------------


class RatingMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    rating_category: str = "seller"  # seller, logistics, lot_quality
    id: str  # target entity ID
    value: int = Field(ge=1, le=5)  # 1 to 5
    feedback: str | None = None


class RatingRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: RatingMessage


class OnRatingMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    seller_score: float | None = None
    feedback_ack: bool = True


class OnRatingRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    context: BecknContext
    message: OnRatingMessage
