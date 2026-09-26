"""API router for computer vision edge assay inference and model registry management."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep, SettingsDep, get_current_user
from app.assay_ai.registry import ModelRegistry
from app.assay_ai.schemas import (
    AssayModelCreate,
    AssayModelResponse,
    AssayReportDetailResponse,
)
from app.assay_ai.service import AssayInferenceService, compute_tamper_evident_hmac
from app.errors import AppError
from app.events.repository import EventRepository
from app.lots.models import AssayReport, Lot

logger = logging.getLogger("app.api.assay")

router = APIRouter(tags=["assay-ai"])


def parse_multipart_form(body: bytes, content_type: str) -> list[tuple[bytes, str | None]]:
    """Parse multipart/form-data payload into list of (bytes, content_type)."""
    if "boundary=" not in content_type:
        return []
    boundary = content_type.split("boundary=")[-1].strip().strip('"').strip("'").encode("ascii")
    boundary_marker = b"--" + boundary
    parts = body.split(boundary_marker)
    extracted: list[tuple[bytes, str | None]] = []

    for part in parts:
        part = part.strip()
        if not part or part == b"--":
            continue
        if b"\r\n\r\n" in part:
            header_bytes, payload = part.split(b"\r\n\r\n", 1)
        elif b"\n\n" in part:
            header_bytes, payload = part.split(b"\n\n", 1)
        else:
            continue

        if payload.endswith(b"\r\n"):
            payload = payload[:-2]
        elif payload.endswith(b"\n"):
            payload = payload[:-1]

        header_str = header_bytes.decode("utf-8", errors="replace")
        part_content_type = None
        for line in header_str.splitlines():
            if line.lower().startswith("content-type:"):
                part_content_type = line.split(":", 1)[1].strip()

        if len(payload) > 0:
            extracted.append((payload, part_content_type))

    return extracted


async def _resolve_lot(session: AsyncSession, lot_id_or_code: str) -> Lot | None:
    """Resolve a Lot by integer ID or string lot_code with assay eagerly loaded."""
    stmt = select(Lot).options(selectinload(Lot.assay))
    if lot_id_or_code.isdigit():
        stmt = stmt.where(or_(Lot.id == int(lot_id_or_code), Lot.lot_code == lot_id_or_code))
    else:
        stmt = stmt.where(Lot.lot_code == lot_id_or_code)
    return (await session.scalars(stmt)).first()


@router.post("/lots/{lot_id}/assay", response_model=AssayReportDetailResponse)
async def submit_lot_assay(
    lot_id: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    user: Any = Depends(get_current_user),
) -> AssayReportDetailResponse:
    """
    Submit 1 to 8 sample images for edge computer vision crop quality assay.
    Performs detection, segmentation, and texture analysis with automatic fallback to AGMARK rules.
    Persists results with tamper-evident HMAC signature and emits AssayCompleted event.
    """
    content_type = request.headers.get("content-type", "")
    body_bytes = await request.body()

    if not body_bytes:
        raise AppError(400, "Image payload is empty")

    image_payloads: list[tuple[bytes, str | None]] = []

    if content_type.startswith("multipart/form-data"):
        image_payloads = parse_multipart_form(body_bytes, content_type)
    elif content_type in ("image/jpeg", "image/png", "image/webp"):
        image_payloads = [(body_bytes, content_type)]
    else:
        # Non-image content type
        raise AppError(415, f"Unsupported Media Type: '{content_type}'. Allowed formats: multipart/form-data with JPEG, PNG, WEBP.")

    if not image_payloads:
        raise AppError(400, "At least 1 image is required for assay evaluation")
    if len(image_payloads) > 8:
        raise AppError(400, f"Maximum 8 images allowed per assay request (received {len(image_payloads)})")

    lot = await _resolve_lot(session, lot_id)
    if lot is None:
        raise AppError(404, f"Lot '{lot_id}' not found")

    # Run inference service
    service = AssayInferenceService(session, settings)
    inference_out, composite_hash = await service.infer_lot_images(
        lot_code=lot.lot_code,
        commodity=lot.commodity,
        images=image_payloads,
    )

    # Compute tamper-evident HMAC signature
    fm_str = f"{Decimal(str(inference_out.foreign_matter_pct)):.2f}"
    moist_str = f"{Decimal(str(inference_out.moisture_estimate)):.2f}"
    dam_str = f"{Decimal(str(inference_out.damaged_kernel_pct)):.2f}"
    hmac_sig = compute_tamper_evident_hmac(
        lot_code=lot.lot_code,
        grade=inference_out.grade,
        foreign_matter=fm_str,
        moisture=moist_str,
        damaged=dam_str,
        image_hash=composite_hash,
        secret=settings.assay_hmac_secret,
    )

    now = datetime.now(UTC)

    # Persist or update assay report record
    if lot.assay is None:
        assay = AssayReport(
            lot_id=lot.id,
            grade=inference_out.grade,
            foreign_matter_percent=Decimal(str(inference_out.foreign_matter_pct)),
            moisture_percent=Decimal(str(inference_out.moisture_estimate)),
            damaged_percent=Decimal(str(inference_out.damaged_kernel_pct)),
            discoloration_severity_score=Decimal(str(inference_out.discoloration_severity_score)),
            pest_infestation_score=Decimal(str(inference_out.pest_infestation_score)),
            grain_size_distribution=inference_out.grain_size_distribution.model_dump(),
            confidence=Decimal(str(inference_out.confidence)),
            image_hash=composite_hash,
            model_versions=inference_out.model_versions,
            fallback=inference_out.fallback,
            hmac_signature=hmac_sig,
            recorded_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(assay)
        lot.assay = assay
    else:
        lot.assay.grade = inference_out.grade
        lot.assay.foreign_matter_percent = Decimal(str(inference_out.foreign_matter_pct))
        lot.assay.moisture_percent = Decimal(str(inference_out.moisture_estimate))
        lot.assay.damaged_percent = Decimal(str(inference_out.damaged_kernel_pct))
        lot.assay.discoloration_severity_score = Decimal(str(inference_out.discoloration_severity_score))
        lot.assay.pest_infestation_score = Decimal(str(inference_out.pest_infestation_score))
        lot.assay.grain_size_distribution = inference_out.grain_size_distribution.model_dump()
        lot.assay.confidence = Decimal(str(inference_out.confidence))
        lot.assay.image_hash = composite_hash
        lot.assay.model_versions = inference_out.model_versions
        lot.assay.fallback = inference_out.fallback
        lot.assay.hmac_signature = hmac_sig
        lot.assay.updated_at = now

    # Record AssayCompleted outbox event for Kafka dispatch
    await EventRepository(session).record_event(
        event_type="AssayCompleted",
        stream_id=f"lot:{lot.lot_code}",
        partition_key=lot.farmer_id,
        payload={
            "lot_code": lot.lot_code,
            "farmer_id": lot.farmer_id,
            "commodity": lot.commodity,
            "grade": inference_out.grade,
            "foreign_matter_percent": str(inference_out.foreign_matter_pct),
            "moisture_percent": str(inference_out.moisture_estimate),
            "damaged_percent": str(inference_out.damaged_kernel_pct),
            "discoloration_severity_score": str(inference_out.discoloration_severity_score),
            "pest_infestation_score": str(inference_out.pest_infestation_score),
            "grain_size_distribution": inference_out.grain_size_distribution.model_dump(),
            "confidence": str(inference_out.confidence),
            "image_hash": composite_hash,
            "model_versions": inference_out.model_versions,
            "fallback": inference_out.fallback,
            "hmac_signature": hmac_sig,
        },
        consent_artifact_id=lot.consent_artifact_id,
    )

    await session.commit()
    await session.refresh(lot.assay)

    return AssayReportDetailResponse(
        lot_code=lot.lot_code,
        farmer_id=lot.farmer_id,
        commodity=lot.commodity,
        grade=lot.assay.grade,
        foreign_matter_percent=lot.assay.foreign_matter_percent,
        moisture_percent=lot.assay.moisture_percent,
        damaged_percent=lot.assay.damaged_percent,
        discoloration_severity_score=lot.assay.discoloration_severity_score,
        pest_infestation_score=lot.assay.pest_infestation_score,
        grain_size_distribution=lot.assay.grain_size_distribution,
        confidence=lot.assay.confidence,
        image_hash=lot.assay.image_hash,
        model_versions=lot.assay.model_versions,
        fallback=lot.assay.fallback,
        hmac_signature=lot.assay.hmac_signature,
        recorded_at=lot.assay.recorded_at,
    )


@router.get("/lots/{lot_id}/assay", response_model=AssayReportDetailResponse)
async def get_lot_assay(
    lot_id: str,
    session: SessionDep,
    user: Any = Depends(get_current_user),
) -> AssayReportDetailResponse:
    """Retrieve the stored, tamper-evident quality assay report for a lot."""
    lot = await _resolve_lot(session, lot_id)
    if lot is None or lot.assay is None:
        raise AppError(404, f"Assay report for lot '{lot_id}' not found")

    return AssayReportDetailResponse(
        lot_code=lot.lot_code,
        farmer_id=lot.farmer_id,
        commodity=lot.commodity,
        grade=lot.assay.grade,
        foreign_matter_percent=lot.assay.foreign_matter_percent,
        moisture_percent=lot.assay.moisture_percent,
        damaged_percent=lot.assay.damaged_percent,
        discoloration_severity_score=lot.assay.discoloration_severity_score,
        pest_infestation_score=lot.assay.pest_infestation_score,
        grain_size_distribution=lot.assay.grain_size_distribution,
        confidence=lot.assay.confidence,
        image_hash=lot.assay.image_hash,
        model_versions=lot.assay.model_versions,
        fallback=lot.assay.fallback,
        hmac_signature=lot.assay.hmac_signature,
        recorded_at=lot.assay.recorded_at,
    )


@router.get("/assay-models", response_model=list[AssayModelResponse])
async def list_assay_models(
    session: SessionDep,
    name: str | None = Query(default=None, description="Filter by role: detector, segmentor, texture"),
    user: Any = Depends(get_current_user),
) -> list[AssayModelResponse]:
    """List registered computer vision assay models and their deployment statuses."""
    registry = ModelRegistry(session)
    models = await registry.list_models(name)
    return [AssayModelResponse.model_validate(m) for m in models]


@router.post("/assay-models", response_model=AssayModelResponse)
async def register_assay_model(
    body: AssayModelCreate,
    session: SessionDep,
    user: Any = Depends(get_current_user),
) -> AssayModelResponse:
    """Register or update an ONNX edge model in the registry."""
    registry = ModelRegistry(session)
    model = await registry.register_model(body)
    return AssayModelResponse.model_validate(model)
