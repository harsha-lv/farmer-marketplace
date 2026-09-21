from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class PriceRecord(BaseModel):
    arrival_date: date
    state: str
    state_lgd_code: str | None
    district: str
    district_lgd_code: str | None
    market: str
    commodity: str
    commodity_group: str | None
    variety: str
    grade: str
    min_price_inr_per_quintal: int
    max_price_inr_per_quintal: int
    modal_price_inr_per_quintal: int
    arrivals_quintal: Decimal | None


class PageMeta(BaseModel):
    limit: int
    offset: int
    count: int


class PriceListResponse(BaseModel):
    data: list[PriceRecord]
    meta: PageMeta


class PriceFilter(BaseModel):
    state: str | None = None
    district: str | None = None
    market: str | None = None
    commodity: str | None = None
    commodity_group: str | None = None
    variety: str | None = None
    grade: str | None = None
    arrival_from: date | None = None
    arrival_to: date | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
