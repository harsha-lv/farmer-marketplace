from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


def _percent(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if value < 0 or value > 100:
        raise ValueError("percentage must be between 0 and 100")
    return value


class LotCreateRequest(BaseModel):
    farmer_id: str = Field(pattern=r"^[A-Za-z0-9-]{6,64}$")
    consent_artifact_id: str = Field(min_length=1, max_length=128)
    commodity: str = Field(min_length=1, max_length=128)
    variety: str = Field(default="", max_length=128)
    quantity_mt: Decimal = Field(gt=0, le=100000)
    grade: str = Field(min_length=1, max_length=64)
    foreign_matter_percent: Decimal | None = None
    moisture_percent: Decimal | None = None
    damaged_percent: Decimal | None = None

    @field_validator("foreign_matter_percent", "moisture_percent", "damaged_percent")
    @classmethod
    def percentage_range(cls, value: Decimal | None) -> Decimal | None:
        return _percent(value)


class AssayResponse(BaseModel):
    grade: str
    foreign_matter_percent: Decimal | None
    moisture_percent: Decimal | None
    damaged_percent: Decimal | None
    recorded_at: datetime


class LotResponse(BaseModel):
    lot_code: str
    farmer_id: str
    commodity: str
    variety: str
    quantity_mt: Decimal
    consent_artifact_id: str
    status: str
    created_at: datetime
    enam_gate_id: str | None = None
    enam_lot_id: str | None = None
    warehouse_id: str | None = None
    warehouse_receipt_id: str | None = None
    assay: AssayResponse


class EnamRegistrationRequest(BaseModel):
    mandi: str = Field(min_length=1, max_length=128)


class WarehouseReceiptRequest(BaseModel):
    warehouse_id: str = Field(min_length=1, max_length=64)


class LotListResponse(BaseModel):
    data: list[LotResponse]
