from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConsentArtifact(Base):
    __tablename__ = "consent_artifacts"
    __table_args__ = (
        UniqueConstraint("artifact_id", name="uq_consent_artifacts_artifact_id"),
        CheckConstraint(
            "status IN ('active', 'withdrawn')",
            name="status_known",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(String(128))
    farmer_id: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(160))
    attributes: Mapped[list[str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signature: Mapped[str] = mapped_column(String(64))
