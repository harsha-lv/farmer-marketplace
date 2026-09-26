from decimal import Decimal, InvalidOperation

import httpx

from app.farmers.farm_id import FarmIdError, validate_farm_id


class RegistryError(Exception):
    """The farmer registry could not be read."""


class ParcelCrop:
    def __init__(self, commodity: str, season: str) -> None:
        self.commodity = commodity
        self.season = season


class LandHolding:
    def __init__(self, farm_id: str, area_hectares: Decimal | None, crops: list[ParcelCrop]) -> None:
        self.farm_id = farm_id
        self.area_hectares = area_hectares
        self.crops = crops


class FarmerProfile:
    def __init__(
        self,
        *,
        farmer_id: str,
        state_lgd_code: str,
        display_name: str,
        parcels: list[LandHolding],
    ) -> None:
        self.farmer_id = farmer_id
        self.state_lgd_code = state_lgd_code
        self.display_name = display_name
        self.parcels = parcels


def _attribute(attributes: dict, *names: str):
    folded = {str(key).casefold().replace("_", ""): value for key, value in attributes.items()}
    for name in names:
        token = name.casefold().replace("_", "")
        if token in folded and folded[token] not in (None, ""):
            return folded[token]
    return None


def parse_profile(body: dict, *, farmer_id: str, state_lgd_code: str) -> FarmerProfile:
    data = body.get("data")
    if not isinstance(data, dict):
        raise RegistryError("farmer registry response has no data")
    attributes = data.get("attributes")
    if not isinstance(attributes, dict):
        raise RegistryError("farmer registry response has no attributes")
    display_name = _attribute(attributes, "displayName", "farmerName", "name")
    if not isinstance(display_name, str) or not display_name.strip():
        raise RegistryError("farmer registry response has no name")
    raw_parcels = _attribute(attributes, "parcels", "landParcels") or []
    if not isinstance(raw_parcels, list):
        raise RegistryError("farmer registry parcels were not a list")
    parcels: list[LandHolding] = []
    for raw in raw_parcels:
        if not isinstance(raw, dict):
            raise RegistryError("farmer registry parcel was not an object")
        farm_id = _attribute(raw, "farmId", "farm_id")
        if not isinstance(farm_id, str):
            raise RegistryError("farmer registry parcel has no farm id")
        try:
            validated = validate_farm_id(farm_id, state_lgd_code=state_lgd_code)
        except FarmIdError as exc:
            raise RegistryError("farmer registry returned an invalid farm id") from exc
        area = _area(_attribute(raw, "areaHectares", "area"))
        crops = _crops(_attribute(raw, "crops") or [])
        parcels.append(LandHolding(validated, area, crops))
    return FarmerProfile(
        farmer_id=farmer_id,
        state_lgd_code=state_lgd_code,
        display_name=display_name.strip(),
        parcels=parcels,
    )


def _area(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        area = Decimal(str(value))
    except InvalidOperation as exc:
        raise RegistryError("farmer registry area is not a number") from exc
    if area < 0:
        raise RegistryError("farmer registry area is negative")
    return area


def _crops(value) -> list[ParcelCrop]:
    if not isinstance(value, list):
        raise RegistryError("farmer registry crops were not a list")
    crops: list[ParcelCrop] = []
    for item in value:
        if not isinstance(item, dict):
            raise RegistryError("farmer registry crop was not an object")
        commodity = _attribute(item, "commodity", "name")
        season = _attribute(item, "season")
        if not isinstance(commodity, str) or not isinstance(season, str):
            raise RegistryError("farmer registry crop is incomplete")
        crops.append(ParcelCrop(commodity.strip(), season.strip()))
    return crops


class UfsiClient:
    def __init__(
        self,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        allow_private: bool | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._transport = transport
        self._allow_private = allow_private if allow_private is not None else (transport is not None)

    async def fetch_profile(
        self,
        *,
        farmer_id: str,
        state_lgd_code: str,
        consent_artifact_id: str,
    ) -> FarmerProfile:
        payload = {
            "data": {
                "type": "farmer-profiles",
                "attributes": {
                    "farmerId": farmer_id,
                    "stateLgdCode": state_lgd_code,
                    "consentArtifact": consent_artifact_id,
                },
            }
        }
        headers = {
            "accept": "application/vnd.api+json",
            "content-type": "application/vnd.api+json",
        }
        try:
            from app.common.http_client import SafeAsyncClient
            from app.errors import AppError

            async with SafeAsyncClient(
                transport=self._transport,
                allow_private=self._allow_private,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/farmerProfileById",
                    json=payload,
                    headers=headers,
                )
        except (httpx.HTTPError, AppError) as exc:
            raise RegistryError("farmer registry request failed") from exc
        if response.status_code >= 400:
            raise RegistryError(f"farmer registry returned {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise RegistryError("farmer registry returned invalid json") from exc
        return parse_profile(body, farmer_id=farmer_id, state_lgd_code=state_lgd_code)
