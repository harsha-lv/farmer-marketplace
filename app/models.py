"""Import domain models so Alembic sees the full metadata."""

from app.prices.models import Commodity, Market, PriceObservation

__all__ = ["Commodity", "Market", "PriceObservation"]
