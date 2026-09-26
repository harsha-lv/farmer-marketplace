"""Edge CV Model Registry managing active, shadow, and deprecated ONNX model artifacts."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assay_ai.models import AssayModel
from app.assay_ai.schemas import AssayModelCreate

logger = logging.getLogger("app.assay_ai.registry")

# Global in-memory cache for loaded ONNX sessions: (model_id, sha256) -> session
_LOADED_SESSIONS: dict[tuple[int, str], Any] = {}


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse semver-like strings into tuples of integers for deterministic version ordering."""
    clean = re.sub(r"[^\d.]", "", version_str)
    parts = clean.split(".")
    try:
        return tuple(int(p) for p in parts if p)
    except ValueError:
        return (0,)


class ModelRegistry:
    """Manages model metadata in PostgreSQL/SQLite and loads ONNX runtime sessions on edge nodes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_model(self, name: str) -> AssayModel | None:
        """
        Return the highest active version for the specified model role (detector, segmentor, texture).
        Falls back gracefully to None if no active models are configured or installed.
        """
        stmt = (
            select(AssayModel)
            .where(AssayModel.name == name, AssayModel.status == "active")
        )
        models = list((await self.session.scalars(stmt)).all())
        if not models:
            return None

        # Sort by semver descending, then by id descending
        models.sort(
            key=lambda m: (parse_version_tuple(m.version), m.id),
            reverse=True,
        )
        return models[0]

    async def get_shadow_models(self, name: str) -> list[AssayModel]:
        """
        Return shadow models that should run in parallel for validation and metrics logging only.
        """
        stmt = (
            select(AssayModel)
            .where(AssayModel.name == name, AssayModel.status == "shadow")
        )
        return list((await self.session.scalars(stmt)).all())

    async def register_model(self, data: AssayModelCreate) -> AssayModel:
        """Register a new edge CV model artifact."""
        model = AssayModel(
            name=data.name,
            version=data.version,
            architecture=data.architecture,
            onnx_path=data.onnx_path,
            sha256=data.sha256,
            input_size=data.input_size,
            class_map=data.class_map,
            metrics=data.metrics,
            status=data.status,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        logger.info(
            "Registered %s model '%s' version %s (status: %s)",
            model.architecture,
            model.name,
            model.version,
            model.status,
        )
        return model

    async def list_models(self, name: str | None = None) -> list[AssayModel]:
        """List registered assay models, optionally filtered by role."""
        stmt = select(AssayModel)
        if name:
            stmt = stmt.where(AssayModel.name == name)
        stmt = stmt.order_by(AssayModel.name.asc(), AssayModel.created_at.desc())
        return list((await self.session.scalars(stmt)).all())

    @staticmethod
    def verify_file_integrity(onnx_path: str, expected_sha256: str) -> bool:
        """Verify on-disk file existence and SHA-256 integrity."""
        p = Path(onnx_path)
        if not p.is_file():
            return False
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest().lower() == expected_sha256.lower()

    @staticmethod
    def load_onnx_session(model: AssayModel) -> Any | None:
        """
        Load an ONNXRuntime InferenceSession.
        Returns None gracefully if onnxruntime is not installed or model file is absent.
        """
        cache_key = (model.id, model.sha256)
        if cache_key in _LOADED_SESSIONS:
            return _LOADED_SESSIONS[cache_key]

        if not Path(model.onnx_path).is_file():
            logger.warning("ONNX weight file not found at %s for model %s", model.onnx_path, model.name)
            return None

        try:
            import onnxruntime as ort
        except ImportError:
            logger.warning("onnxruntime is not installed; running in stub/fallback mode.")
            return None

        try:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            available = ort.get_available_providers()
            active_providers = [p for p in providers if p in available]
            sess = ort.InferenceSession(model.onnx_path, providers=active_providers)
            _LOADED_SESSIONS[cache_key] = sess
            logger.info("Loaded ONNX session for %s %s with providers %s", model.name, model.version, active_providers)
            return sess
        except Exception as exc:
            logger.error("Failed to initialize ONNX session for %s: %s", model.onnx_path, exc)
            return None
