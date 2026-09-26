"""AgriStack Crop Sown Registry Verification and Provenance Engine.

Validates that agricultural lots offered for trade or warehouse pledge loans
originate from government-verified land parcels registered in the AgriStack
Crop Sown Registry, confirming cultivated commodity, survey acreage, and
agronomic yield capacity.
"""

import hashlib
import hmac
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.farmers.models import Farmer

# Standard benchmark agronomic yields (Metric Tons per Hectare) based on ICAR & AGMARKNET norms
DEFAULT_CROP_YIELDS_MT_PER_HA: dict[str, Decimal] = {
    "onion": Decimal("18.0"),
    "potato": Decimal("22.0"),
    "tomato": Decimal("25.0"),
    "wheat": Decimal("3.5"),
    "paddy": Decimal("4.0"),
    "rice": Decimal("4.0"),
    "mustard": Decimal("1.5"),
    "rapeseed": Decimal("1.5"),
    "soybean": Decimal("1.8"),
    "cotton": Decimal("2.0"),
    "maize": Decimal("3.2"),
    "corn": Decimal("3.2"),
    "chana": Decimal("1.2"),
    "gram": Decimal("1.2"),
    "pulses": Decimal("1.2"),
    "groundnut": Decimal("2.0"),
    "sugarcane": Decimal("75.0"),
}

DEFAULT_FALLBACK_YIELD_MT_PER_HA = Decimal("3.0")


@dataclass(frozen=True)
class CropSownVerificationResult:
    farmer_id: str
    commodity: str
    is_cultivation_verified: bool
    verification_status: str  # VERIFIED, UNVERIFIED_COMMODITY, EXCEEDS_CAPACITY
    matched_parcels: list[str]
    total_cultivated_area_hectares: Decimal
    estimated_max_yield_mt: Decimal
    authenticity_certificate: str
    survey_season: str
    rationale: str


def get_benchmark_yield(commodity: str) -> Decimal:
    """Return benchmark agronomic yield in MT/hectare for the commodity."""
    clean = commodity.strip().casefold()
    for key, yield_val in DEFAULT_CROP_YIELDS_MT_PER_HA.items():
        if key in clean or clean in key:
            return yield_val
    return DEFAULT_FALLBACK_YIELD_MT_PER_HA


def generate_authenticity_certificate(
    *,
    farmer_id: str,
    commodity: str,
    verification_status: str,
    total_area_hectares: Decimal,
    matched_parcels: Sequence[str],
    secret_key: str,
) -> str:
    """Generate a tamper-evident HMAC-SHA256 authenticity certificate."""
    parcels_str = ",".join(sorted(matched_parcels))
    payload = f"FARMER={farmer_id}|COMMODITY={commodity.upper()}|STATUS={verification_status}|AREA={total_area_hectares}|PARCELS={parcels_str}"
    mac = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    )
    return mac.hexdigest()


def verify_crop_cultivation(
    farmer: Farmer,
    *,
    commodity: str,
    season: str | None = None,
    claimed_quantity_mt: Decimal | None = None,
    secret_key: str = "agristack-verification-key",
) -> CropSownVerificationResult:
    """Verify that a commodity originates from verified AgriStack Crop Sown parcels.

    Args:
        farmer: The loaded Farmer entity containing land parcels and crop survey records.
        commodity: The crop commodity being listed or traded (e.g. "Wheat", "Onion").
        season: Optional agricultural season filter (e.g. "Kharif", "Rabi").
        claimed_quantity_mt: Optional physical volume to validate against land capacity.
        secret_key: Secret used to mint the digital authenticity certificate.

    Returns:
        CropSownVerificationResult: Verification determination and proof of provenance.
    """
    comm_clean = commodity.strip().casefold()
    season_clean = season.strip().casefold() if season else None

    matched_parcels: list[str] = []
    total_area = Decimal(0)
    detected_seasons: set[str] = set()

    for parcel in farmer.parcels:
        parcel_matched = False
        for crop in parcel.crops:
            crop_name_clean = crop.commodity.strip().casefold()
            name_match = (
                comm_clean == crop_name_clean
                or comm_clean in crop_name_clean
                or crop_name_clean in comm_clean
            )
            if not name_match:
                continue

            crop_season_clean = crop.season.strip().casefold()
            if season_clean and season_clean != crop_season_clean:
                continue

            parcel_matched = True
            detected_seasons.add(crop.season.strip())

        if parcel_matched:
            matched_parcels.append(parcel.farm_id)
            if parcel.area_hectares is not None and parcel.area_hectares > Decimal(0):
                total_area += parcel.area_hectares

    survey_season = ", ".join(sorted(detected_seasons)) if detected_seasons else (season or "Current Season")
    benchmark_yield = get_benchmark_yield(commodity)
    estimated_max_yield = (total_area * benchmark_yield).quantize(Decimal("0.01"))

    if not matched_parcels:
        cert = generate_authenticity_certificate(
            farmer_id=farmer.farmer_id,
            commodity=commodity,
            verification_status="UNVERIFIED_COMMODITY",
            total_area_hectares=Decimal(0),
            matched_parcels=[],
            secret_key=secret_key,
        )
        return CropSownVerificationResult(
            farmer_id=farmer.farmer_id,
            commodity=commodity,
            is_cultivation_verified=False,
            verification_status="UNVERIFIED_COMMODITY",
            matched_parcels=[],
            total_cultivated_area_hectares=Decimal(0),
            estimated_max_yield_mt=Decimal(0),
            authenticity_certificate=cert,
            survey_season=survey_season,
            rationale=(
                f"Commodity '{commodity}' is not registered in the AgriStack Crop Sown Registry "
                f"for farmer '{farmer.farmer_id}' across any verified land parcels."
            ),
        )

    # Check capacity constraints if claimed volume is provided
    status = "VERIFIED"
    is_verified = True
    rationale = (
        f"Verified {commodity} cultivation across {len(matched_parcels)} parcel(s) "
        f"totaling {total_area} hectares ({survey_season}) with estimated yield of {estimated_max_yield} MT."
    )

    if claimed_quantity_mt is not None and claimed_quantity_mt > Decimal(0):
        # Allow up to 150% of benchmark yield to accommodate superior farming techniques
        capacity_limit = (estimated_max_yield * Decimal("1.50")).quantize(Decimal("0.01"))
        if claimed_quantity_mt > capacity_limit:
            status = "EXCEEDS_CAPACITY"
            # Note: cultivation is verified, but volume exceeds normal parcel capacity
            rationale = (
                f"Claimed volume {claimed_quantity_mt} MT exceeds the estimated agronomic production "
                f"capacity of {estimated_max_yield} MT (upper threshold {capacity_limit} MT) across "
                f"{total_area} hectares. Secondary assayer audit recommended."
            )

    cert = generate_authenticity_certificate(
        farmer_id=farmer.farmer_id,
        commodity=commodity,
        verification_status=status,
        total_area_hectares=total_area,
        matched_parcels=matched_parcels,
        secret_key=secret_key,
    )

    return CropSownVerificationResult(
        farmer_id=farmer.farmer_id,
        commodity=commodity,
        is_cultivation_verified=is_verified,
        verification_status=status,
        matched_parcels=matched_parcels,
        total_cultivated_area_hectares=total_area,
        estimated_max_yield_mt=estimated_max_yield,
        authenticity_certificate=cert,
        survey_season=survey_season,
        rationale=rationale,
    )
