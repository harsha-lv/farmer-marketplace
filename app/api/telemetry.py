from typing import Annotated

from fastapi import APIRouter, Depends

from app.errors import AppError
from app.telemetry.jetstream import NatsJetStreamEngine, get_jetstream_engine
from app.telemetry.rpc import BecknRpcBroker, get_beckn_rpc_broker
from app.telemetry.schemas import (
    BecknRpcRequest,
    BecknRpcResponse,
    EdgeTelemetryPayload,
    FpoStreamInfo,
    FpoStreamProvisionRequest,
    TelemetryIngestResponse,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def get_engine() -> NatsJetStreamEngine:
    return get_jetstream_engine()


def get_broker() -> BecknRpcBroker:
    return get_beckn_rpc_broker()


EngineDep = Annotated[NatsJetStreamEngine, Depends(get_engine)]
BrokerDep = Annotated[BecknRpcBroker, Depends(get_broker)]


@router.post("/edge")
async def ingest_edge_telemetry(
    payload: EdgeTelemetryPayload,
    engine: EngineDep,
) -> TelemetryIngestResponse:
    subject = f"fpo.{payload.fpo_id}.telemetry.{payload.telemetry_type}"
    msg_id = f"telem_{payload.device_id}_{int(payload.timestamp.timestamp())}"
    message = await engine.publish(
        subject=subject,
        payload=payload.model_dump(mode="json"),
        headers={
            "FPO-ID": payload.fpo_id,
            "Device-ID": payload.device_id,
            "Telemetry-Type": payload.telemetry_type,
        },
        msg_id=msg_id,
    )
    return TelemetryIngestResponse(
        status="ACCEPTED",
        stream_name=message.stream,
        stream_seq=message.seq,
        msg_id=message.msg_id,
        subject=message.subject,
        timestamp=message.timestamp,
    )


@router.post("/streams/{fpo_id}/provision")
async def provision_fpo_stream(
    fpo_id: str,
    engine: EngineDep,
    request: FpoStreamProvisionRequest | None = None,
) -> FpoStreamInfo:
    max_msgs = request.max_messages if request else None
    max_bytes = request.max_bytes if request else None
    max_age = request.max_age_seconds if request else None
    dedup = request.duplicate_window_seconds if request else None

    await engine.provision_fpo_stream(
        fpo_id=fpo_id,
        max_messages=max_msgs,
        max_bytes=max_bytes,
        max_age_seconds=max_age,
        duplicate_window_seconds=dedup,
    )
    info = engine.get_stream_info(fpo_id)
    if info is None:
        raise AppError(500, "Failed to retrieve stream info after provisioning")
    return info


@router.get("/streams/{fpo_id}")
async def get_fpo_stream_info(
    fpo_id: str,
    engine: EngineDep,
) -> FpoStreamInfo:
    info = engine.get_stream_info(fpo_id)
    if info is None:
        raise AppError(404, f"Stream for FPO {fpo_id} not found")
    return info


@router.post("/rpc/beckn")
async def dispatch_beckn_rpc(
    request: BecknRpcRequest,
    broker: BrokerDep,
) -> BecknRpcResponse:
    return await broker.dispatch_request(request)
