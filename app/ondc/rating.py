"""Rating service for post-fulfillment seller, logistics, and lot quality evaluations."""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ondc.models import RatingRecord

logger = logging.getLogger("app.ondc.rating")


class RatingService:
    """Manages buyer ratings and computes weighted seller reputation scores."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit_rating(
        self,
        transaction_id: str,
        target_id: str,
        score: int,
        rating_category: str = "seller",
        feedback: str | None = None,
    ) -> RatingRecord:
        """Persist buyer rating and update seller score."""
        score = min(max(int(score), 1), 5)
        record = RatingRecord(
            transaction_id=transaction_id,
            target_id=target_id,
            rating_category=rating_category.lower(),
            score=score,
            feedback=feedback,
            created_at=datetime.now(UTC),
        )
        self.session.add(record)
        await self.session.commit()
        logger.info("Recorded %s rating (%d/5) for target %s on tx %s", rating_category, score, target_id, transaction_id)
        return record

    async def get_seller_score(self, target_id: str) -> float:
        """Compute average reputation score for a seller/provider (1.0 to 5.0)."""
        stmt = (
            select(func.avg(RatingRecord.score), func.count(RatingRecord.id))
            .where(RatingRecord.target_id == target_id)
        )
        row = (await self.session.execute(stmt)).first()
        if row and row[0] is not None:
            return round(float(row[0]), 2)
        return 4.0  # Default initial baseline score for new sellers

    async def list_ratings(self, target_id: str) -> list[RatingRecord]:
        """Fetch all ratings for a given entity."""
        stmt = select(RatingRecord).where(RatingRecord.target_id == target_id).order_by(RatingRecord.created_at.desc())
        return list((await self.session.scalars(stmt)).all())
