"""Pydantic v2 schemas for computer vision assay models and inference responses."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GrainSizeDistribution(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    p10: float = Field(..., description="10th percentile grain length/diameter in mm")
    p50: float = Field(..., description="Median grain length/diameter in mm")
    p90: float = Field(..., description="90th percentile grain length/diameter in mm")


class AssayInferenceOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    foreign_matter_pct: float = Field(..., ge=0.0, le=100.0)
    grain_size_distribution: GrainSizeDistribution
    damaged_kernel_pct: float = Field(..., ge=0.0, le=100.0)
    discoloration_severity_score: float = Field(..., ge=0.0, le=100.0)
    pest_infestation_score: float = Field(..., ge=0.0, le=100.0)
    moisture_estimate: float = Field(..., ge=0.0, le=100.0)
    grade: Literal["A", "B", "C"] = Field(..., description="Certified AGMARK / e-NAM grade")
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_versions: dict[str, str] | None = Field(default=None, description="Versions of detector, segmentor, and texture models")
    fallback: str | None = Field(default=None, description="Fallback engine when models are not installed (e.g. 'rule_based')")


class AssayModelCreate(BaseModel):
    name: Literal["detector", "segmentor", "texture"]
    version: str = Field(..., min_length=1, max_length=32)
    architecture: str = Field(..., min_length=1, max_length=64)
    onnx_path: str = Field(..., min_length=1, max_length=255)
    sha256: str = Field(..., min_length=64, max_length=64)
    input_size: list[int] | None = Field(default=[1, 3, 352, 352])
    class_map: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    status: Literal["active", "shadow", "deprecated"] = "active"


class AssayModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    version: str
    architecture: str
    onnx_path: str
    sha256: str
    input_size: list[int] | None = None
    class_map: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    status: str
    created_at: datetime


class AssayReportDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    lot_code: str
    farmer_id: str
    commodity: str
    grade: str
    foreign_matter_percent: Decimal | None = None
    moisture_percent: Decimal | None = None
    damaged_percent: Decimal | None = None
    discoloration_severity_score: Decimal | None = None
    pest_infestation_score: Decimal | None = None
    grain_size_distribution: dict[str, Any] | None = None
    confidence: Decimal | None = None
    image_hash: str | None = None
    model_versions: dict[str, Any] | None = None
    fallback: str | None = None
    hmac_signature: str | None = None
    recorded_at: datetime
