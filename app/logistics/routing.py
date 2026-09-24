import math
from typing import Sequence

from app.logistics.schemas import (
    Coordinates,
    FacilityAllocationRequest,
    FacilityAllocationResponse,
    FacilityPoint,
    RouteCalculationRequest,
    RouteCalculationResponse,
)

ROAD_FACTOR = 1.28
SPEED_PROFILES: dict[str, float] = {
    "TRACTOR_TROLLEY": 25.0,
    "LITTLE_TRUCK": 35.0,
    "MEDIUM_TRUCK": 42.0,
    "HEAVY_TRUCK": 48.0,
}


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on the earth in kilometers."""
    r = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


def estimate_road_distance_km(geodesic_km: float) -> float:
    """Estimate real road distance applying tortuosity factor."""
    return round(geodesic_km * ROAD_FACTOR, 2)


def estimate_transit_hours(road_distance_km: float, vehicle_type: str) -> float:
    """Estimate transit duration in hours based on vehicle speed profile."""
    speed = SPEED_PROFILES.get(vehicle_type.upper(), 40.0)
    if speed <= 0:
        speed = 40.0
    return round(road_distance_km / speed, 2)


def calculate_freight_quote(request: RouteCalculationRequest) -> RouteCalculationResponse:
    """Calculate detailed P2P freight logistics quote."""
    geo_km = haversine_distance_km(
        request.origin.latitude,
        request.origin.longitude,
        request.destination.latitude,
        request.destination.longitude,
    )
    road_km = estimate_road_distance_km(geo_km)
    transit_hrs = estimate_transit_hours(road_km, request.vehicle_type)

    base_charge = 500  # Minimum operational flagfall fee
    rate_per_q_km = 4.50 if request.requires_cold_chain else 3.50
    dist_charge = int(round(request.quantity_quintals * road_km * rate_per_q_km))

    cold_surcharge = int(round(dist_charge * 0.25)) if request.requires_cold_chain else 0
    total = base_charge + dist_charge + cold_surcharge

    return RouteCalculationResponse(
        geodesic_distance_km=geo_km,
        estimated_road_distance_km=road_km,
        estimated_transit_hours=transit_hrs,
        base_charge_inr=base_charge,
        distance_charge_inr=dist_charge,
        cold_chain_surcharge_inr=cold_surcharge,
        total_freight_inr=total,
        freight_rate_per_quintal_km_inr=rate_per_q_km,
    )


def score_facility(
    facility: FacilityPoint,
    distance_km: float,
    request: FacilityAllocationRequest,
) -> float:
    """Calculate 0-100 composite suitability score for warehouse/mandi allocation."""
    # Distance component: 50% max weight (decaying linearly with max_radius_km)
    dist_fraction = min(1.0, distance_km / max(1.0, request.max_radius_km))
    dist_score = max(0.0, 50.0 * (1.0 - dist_fraction))

    # Capacity component: 25% weight
    if facility.available_quintals >= request.quantity_quintals:
        cap_score = 25.0
    else:
        # Partial capacity proportional score
        cap_score = 25.0 * (facility.available_quintals / max(1.0, request.quantity_quintals))

    # Intent and capability component: 25% weight
    intent = request.intent.upper()
    intent_score = 0.0
    if intent == "STORAGE":
        if facility.facility_type in {"WAREHOUSE", "COLD_STORAGE"}:
            intent_score += 15.0
            if facility.wdra_registration_no:
                intent_score += 5.0
            if request.requires_cold_chain:
                intent_score += 5.0 if facility.cold_storage else -15.0
    elif intent == "SALE":
        if facility.facility_type == "MANDI":
            intent_score += 25.0
        else:
            intent_score += 5.0

    total_score = max(0.0, min(100.0, dist_score + cap_score + intent_score))
    return round(total_score, 2)


def rank_and_allocate_facilities(
    facilities: Sequence[FacilityPoint],
    request: FacilityAllocationRequest,
) -> FacilityAllocationResponse:
    """Filter, rank, and allocate the optimal facility based on location, capacity, and intent."""
    scored_facilities: list[FacilityPoint] = []

    for fac in facilities:
        dist_km = haversine_distance_km(
            request.origin.latitude,
            request.origin.longitude,
            fac.latitude,
            fac.longitude,
        )
        if dist_km > request.max_radius_km:
            continue

        if request.requires_cold_chain and not fac.cold_storage and request.intent == "STORAGE":
            # Exclude non-cold storage if cold chain is explicitly requested for storage
            continue

        score = score_facility(fac, dist_km, request)
        fac_copy = fac.model_copy()
        fac_copy.distance_km = dist_km
        fac_copy.suitability_score = score
        scored_facilities.append(fac_copy)

    # Sort descending by suitability score, then ascending by distance
    scored_facilities.sort(key=lambda f: (-(f.suitability_score or 0.0), f.distance_km or 99999.0))
    top_facilities = scored_facilities[: request.limit]

    if not top_facilities:
        return FacilityAllocationResponse(
            origin=request.origin,
            intent=request.intent,
            recommended_facility_id=None,
            recommended_facility_name=None,
            reason=f"No suitable facility found within {request.max_radius_km} km radius matching criteria.",
            facilities=[],
        )

    best = top_facilities[0]
    reason = (
        f"Selected {best.name} ({best.facility_type}) as optimal destination: "
        f"{best.distance_km} km away, suitability score {best.suitability_score}/100. "
        f"Available capacity: {best.available_quintals} quintals."
    )
    if best.wdra_registration_no:
        reason += f" WDRA Reg: {best.wdra_registration_no} (eNWR eligible)."

    return FacilityAllocationResponse(
        origin=request.origin,
        intent=request.intent,
        recommended_facility_id=best.id,
        recommended_facility_name=best.name,
        reason=reason,
        facilities=top_facilities,
    )
