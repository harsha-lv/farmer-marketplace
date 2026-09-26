"""SQLAlchemy data models for edge computer vision assay models registry."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class AssayModel(Base):
    """Registry entry for an ONNX edge CV model (detector, segmentor, or texture)."""

    __tablename__ = "assay_models"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_assay_models_name_version"),
        Index("ix_assay_models_name_status", "name", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        autoincrement=True,
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(64), index=True)  # detector | segmentor | texture
    version: Mapped[str] = mapped_column(String(32), index=True)  # e.g., "1.0.0"
    architecture: Mapped[str] = mapped_column(String(64))  # e.g., "YOLO-FastestV2+ECA+EMA+SimLightFPN"
    onnx_path: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    input_size: Mapped[list[int] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    class_map: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)  # active | shadow | deprecated
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
