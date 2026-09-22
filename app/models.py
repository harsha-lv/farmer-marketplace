"""Import domain models so Alembic sees the full metadata."""

from app.farmers.models import CropRecord, Farmer, LandParcel
from app.prices.models import Commodity, Market, PriceObservation

__all__ = [
    "Commodity",
    "CropRecord",
    "Farmer",
    "LandParcel",
    "Market",
    "PriceObservation",
]
