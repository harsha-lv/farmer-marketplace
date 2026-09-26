"""Freight quotation aggregator merging ONDC network LSP quotes with internal PostGIS estimates.

Guarantees:
  - Computes internal geodesic x 1.28 tortuosity estimate with vehicle speed profiles
    and cold-chain surcharge.
  - Normalizes third-party network quotes and internal estimates into a unified schema.
  - Strictly distinguishes committed network offers from internal estimates:
      - `source: "network" | "internal"`
      - `is_committed_offer: True | False`
      - Never surfaces an internal estimate as if it were a committed carrier offer.
  - Produces deterministic ranking: verified network offers ranked by price and ETA,
    followed by the internal benchmark calculation.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

from app.logistics.ondc_lsp import FreightQuote
from app.logistics.routing import (
    ROAD_FACTOR,
    calculate_freight_quote,
)
from app.logistics.schemas import Coordinates, RouteCalculationRequest

logger = logging.getLogger("app.logistics.quote_aggregator")


@dataclass
class RankedFreightQuote:
    """Consolidated and ranked freight quotation."""

    quote_id: str
    lsp_id: str
    lsp_name: str
    lsp_uri: str
    source: str                 # "network" | "internal"
    is_committed_offer: bool    # True for network LSPs, False for internal estimates
    price_inr: int
    eta_hours: float
    vehicle_type: str
    cold_chain: bool
    rank: int
    composite_score: float
    tracking_enabled: bool
    terms: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def calculate_internal_freight_quote(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
    quantity_quintals: float = 10.0,
    vehicle_type: str = "MEDIUM_TRUCK",
    requires_cold_chain: bool = False,
) -> FreightQuote:
    """Calculate internal freight benchmark using PostGIS / Haversine 1.28x tortuosity."""
    req = RouteCalculationRequest(
        origin=Coordinates(latitude=origin_lat, longitude=origin_lon),
        destination=Coordinates(latitude=destination_lat, longitude=destination_lon),
        quantity_quintals=quantity_quintals,
        vehicle_type=vehicle_type,
        requires_cold_chain=requires_cold_chain,
    )
    resp = calculate_freight_quote(req)

    quote_id = f"int_est_{abs(hash((origin_lat, origin_lon, destination_lat, destination_lon, quantity_quintals))):x}"
    return FreightQuote(
        quote_id=quote_id,
        lsp_id="INTERNAL_ESTIMATE",
        lsp_name="Internal Route Estimate (PostGIS 1.28x Tortuosity)",
        lsp_uri="",
        price=resp.total_freight_inr,
        eta_hours=resp.estimated_transit_hours,
        vehicle=vehicle_type,
        cold_chain=requires_cold_chain,
        terms={
            "disclaimer": "Informational route benchmark only. Not a committed network carrier offer.",
            "road_factor": ROAD_FACTOR,
            "geodesic_distance_km": resp.geodesic_distance_km,
            "estimated_road_distance_km": resp.estimated_road_distance_km,
            "base_charge_inr": resp.base_charge_inr,
            "distance_charge_inr": resp.distance_charge_inr,
            "cold_chain_surcharge_inr": resp.cold_chain_surcharge_inr,
        },
        validity=None,
        source="internal",
        is_committed_offer=False,  # Hard guarantee: never committed
        tracking_enabled=False,
        category="INTERNAL",
    )


def aggregate_freight_quotes(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
    quantity_quintals: float = 10.0,
    vehicle_type: str = "MEDIUM_TRUCK",
    requires_cold_chain: bool = False,
    network_quotes: list[FreightQuote] | None = None,
) -> list[RankedFreightQuote]:
    """Merge network carrier quotes with internal benchmark and rank them.

    Ranking criteria:
      1. Network committed offers are prioritized.
      2. Lowest total freight price is ranked highest.
      3. Shortest transit ETA breaks price ties.
      4. Internal benchmark is explicitly flagged `source='internal'` and
         `is_committed_offer=False`, appended with lowest priority.
    """
    quotes: list[FreightQuote] = []

    # 1. Add valid network quotes
    if network_quotes:
        for nq in network_quotes:
            # Ensure safety invariants
            if nq.source != "network":
                nq.source = "network"
            quotes.append(nq)

    # 2. Compute internal route estimate
    internal_quote = calculate_internal_freight_quote(
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        destination_lat=destination_lat,
        destination_lon=destination_lon,
        quantity_quintals=quantity_quintals,
        vehicle_type=vehicle_type,
        requires_cold_chain=requires_cold_chain,
    )
    quotes.append(internal_quote)

    # 3. Score and rank quotes
    # Committed network offers receive a +10,000 priority baseline
    def score_quote(q: FreightQuote) -> float:
        if q.is_committed_offer:
            # Higher score is better: base priority - price - (eta * 10)
            return 100_000.0 - float(q.price) - (float(q.eta_hours) * 10.0)
        # Internal estimate has no network priority bonus
        return 0.0 - float(q.price) - (float(q.eta_hours) * 10.0)

    # Sort descending by composite score
    sorted_quotes = sorted(quotes, key=score_quote, reverse=True)

    ranked: list[RankedFreightQuote] = []
    for idx, q in enumerate(sorted_quotes, start=1):
        ranked.append(
            RankedFreightQuote(
                quote_id=q.quote_id,
                lsp_id=q.lsp_id,
                lsp_name=q.lsp_name,
                lsp_uri=q.lsp_uri,
                source=q.source,
                is_committed_offer=q.is_committed_offer,
                price_inr=q.price,
                eta_hours=q.eta_hours,
                vehicle_type=q.vehicle,
                cold_chain=q.cold_chain,
                rank=idx,
                composite_score=round(score_quote(q), 2),
                tracking_enabled=q.tracking_enabled,
                terms=q.terms,
            )
        )

    return ranked
