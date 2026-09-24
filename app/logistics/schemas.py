from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class RouteCalculationRequest(BaseModel):
    origin: Coordinates
    destination: Coordinates
    quantity_quintals: float = Field(default=10.0, gt=0)
    vehicle_type: str = Field(
        default="MEDIUM_TRUCK",
        description="LITTLE_TRUCK, MEDIUM_TRUCK, HEAVY_TRUCK, TRACTOR_TROLLEY",
    )
    requires_cold_chain: bool = False


class RouteCalculationResponse(BaseModel):
    geodesic_distance_km: float
    estimated_road_distance_km: float
    estimated_transit_hours: float
    base_charge_inr: int
    distance_charge_inr: int
    cold_chain_surcharge_inr: int
    total_freight_inr: int
    freight_rate_per_quintal_km_inr: float


class FacilityPoint(BaseModel):
    id: int
    name: str
    facility_type: str
    wdra_registration_no: str | None = None
    state: str
    district: str
    pincode: str | None = None
    latitude: float
    longitude: float
    capacity_quintals: float
    available_quintals: float
    cold_storage: bool = False
    daily_charge_inr_per_quintal: float
    distance_km: float | None = None
    suitability_score: float | None = None


class FacilityAllocationRequest(BaseModel):
    origin: Coordinates
    quantity_quintals: float = Field(gt=0)
    intent: str = Field(
        default="STORAGE",
        description="STORAGE or SALE",
    )
    requires_cold_chain: bool = False
    max_radius_km: float = Field(default=100.0, ge=1.0, le=500.0)
    limit: int = Field(default=5, ge=1, le=50)


class FacilityAllocationResponse(BaseModel):
    origin: Coordinates
    intent: str
    recommended_facility_id: int | None = None
    recommended_facility_name: str | None = None
    reason: str
    facilities: list[FacilityPoint]


class FacilityCreateRequest(BaseModel):
    name: str
    facility_type: str
    wdra_registration_no: str | None = None
    state: str
    district: str
    pincode: str | None = None
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    capacity_quintals: float = Field(gt=0)
    available_quintals: float = Field(ge=0)
    cold_storage: bool = False
    daily_charge_inr_per_quintal: float = Field(default=0.50, ge=0)
