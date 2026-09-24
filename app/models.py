"""Import domain models so Alembic sees the full metadata."""

from app.consent.models import ConsentArtifact
from app.farmers.models import CropRecord, Farmer, LandParcel
from app.lots.models import AssayReport, Lot
from app.events.models import OutboxEvent
from app.prices.models import Commodity, Market, PriceObservation
from app.trades.models import ErupiVoucher, SettlementRecord, TradeContract

__all__ = [
    "Commodity",
    "ConsentArtifact",
    "CropRecord",
    "AssayReport",
    "ErupiVoucher",
    "Farmer",
    "LandParcel",
    "Lot",
    "Market",
    "OutboxEvent",
    "PriceObservation",
    "SettlementRecord",
    "TradeContract",
]
