from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.consent.models import ConsentArtifact
from app.consent.signing import ConsentRecord
from app.farmers.models import Farmer


class ConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, artifact_id: str) -> ConsentArtifact | None:
        statement = select(ConsentArtifact).where(ConsentArtifact.artifact_id == artifact_id)
        return await self.session.scalar(statement)

    async def add(self, artifact: ConsentArtifact) -> ConsentArtifact:
        self.session.add(artifact)
        await self.session.flush()
        return artifact

    async def delete_profile(self, farmer_id: str, artifact_id: str) -> None:
        await self.session.execute(
            delete(Farmer).where(
                Farmer.farmer_id == farmer_id,
                Farmer.consent_artifact_id == artifact_id,
            )
        )

    @staticmethod
    def record(artifact: ConsentArtifact) -> ConsentRecord:
        return ConsentRecord(
            artifact_id=artifact.artifact_id,
            farmer_id=artifact.farmer_id,
            purpose=artifact.purpose,
            attributes=tuple(artifact.attributes),
            created_at=artifact.created_at,
            expires_at=artifact.expires_at,
            status=artifact.status,
        )


def utcnow() -> datetime:
    return datetime.now(UTC)
