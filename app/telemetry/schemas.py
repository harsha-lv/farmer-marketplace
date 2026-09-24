from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class EdgeMetrics(BaseModel):
    battery_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    temperature_c: float | None = Field(default=None, ge=-40.0, le=85.0)
    humidity_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    gps_lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    gps_lon: float | None = Field(default=None, ge=-180.0, le=180.0)
    inference_fps: float | None = Field(default=None, ge=0.0)
    model_version: str | None = Field(default=None, max_length=64)
    power_watts: float | None = Field(default=None, ge=0.0, le=100.0)


class EdgeTelemetryPayload(BaseModel):
    fpo_id: str = Field(min_length=2, max_length=64)
    device_id: str = Field(min_length=2, max_length=64)
    telemetry_type: Literal["sensor", "assay_inference", "sync_event", "heartbeat"]
    timestamp: datetime
    metrics: EdgeMetrics = Field(default_factory=EdgeMetrics)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value


class TelemetryIngestResponse(BaseModel):
    status: str = "ACCEPTED"
    stream_name: str
    stream_seq: int
    msg_id: str
    subject: str
    timestamp: datetime


class FpoStreamProvisionRequest(BaseModel):
    fpo_id: str = Field(min_length=2, max_length=64)
    max_messages: int | None = Field(default=None, ge=100)
    max_bytes: int | None = Field(default=None, ge=1024)
    max_age_seconds: int | None = Field(default=None, ge=60)
    duplicate_window_seconds: int | None = Field(default=None, ge=1)


class FpoStreamInfo(BaseModel):
    stream_name: str
    fpo_id: str
    subjects: list[str]
    message_count: int
    byte_count: int
    first_seq: int
    last_seq: int
    consumer_count: int
    created_at: datetime


class BecknRpcRequest(BaseModel):
    domain: str = "ONDC:AGR10"
    action: str = Field(min_length=1, max_length=64)
    bap_id: str = Field(min_length=1, max_length=128)
    bap_uri: str = Field(min_length=1, max_length=256)
    transaction_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=5000, ge=100, le=30000)


class BecknRpcResponse(BaseModel):
    status: Literal["SUCCESS", "TIMEOUT", "ERROR"]
    action: str
    transaction_id: str
    message_id: str
    reply_subject: str
    response_payload: dict[str, Any] | None = None
    error_message: str | None = None
    latency_ms: float = 0.0
