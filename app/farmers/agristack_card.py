"""AgriStack Digital Farmer Card Client and Proxy.

Implements the official AgriStack DPI interface:
    GET /agristack/newcard.php?api_key=...&aadhar=...&state=...
to retrieve digitized e-Pehchan Farmer Card profiles, digital signatures,
land records, and crop survey registrations.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import re
from typing import Any

import httpx

from app.farmers.farm_id import FarmIdError, validate_farm_id
from app.farmers.ufsi import LandHolding, ParcelCrop, _area, _attribute, _crops
from app.prices.lgd import canonical_state_lgd_code


class AgristackCardError(Exception):
    """The AgriStack digital card service returned an error or invalid response."""


def mask_aadhar(aadhar: str) -> str:
    """Mask Aadhaar number according to UIDAI and DPDP Act statutory requirements.

    Never stores or logs the 12-digit plain Aadhaar. Preserves only the last 4 digits.
    """
    clean = re.sub(r"[\s\-]", "", aadhar.strip())
    if clean.upper().startswith("X") and len(clean) >= 4:
        # Already masked like XXXXXXXX1234
        return f"XXXXXXXX{clean[-4:]}"
    if not clean.isdigit() or len(clean) < 4:
        raise AgristackCardError("Aadhaar identifier must contain at least 4 digits")
    return f"XXXXXXXX{clean[-4:]}"


@dataclass(frozen=True)
class AgristackCardData:
    farmer_id: str
    application_no: str
    state_lgd_code: str
    state_name: str
    district_name: str | None
    display_name: str
    masked_aadhar: str
    gender: str | None
    dob_or_age: str | None
    card_status: str
    pdf_download_url: str | None
    qr_code_payload: str
    parcels: list[LandHolding]
    crop_summary: list[str]
    fetched_at: datetime


def parse_card_response(body: dict[str, Any], *, fallback_state: str) -> AgristackCardData:
    """Parse and validate the JSON payload returned by /agristack/newcard.php."""
    if not isinstance(body, dict):
        raise AgristackCardError("AgriStack card response is not a valid JSON object")

    # Some versions return {"status": "SUCCESS", "data": {...}}, others return root attributes
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        raise AgristackCardError("AgriStack card payload contains no data attributes")

    status = _attribute(body, "status") or _attribute(data, "cardStatus", "status") or "ACTIVE"
    if str(status).upper() in ("FAIL", "FAILURE", "ERROR"):
        msg = _attribute(body, "message", "error") or "AgriStack rejected card request"
        raise AgristackCardError(str(msg))

    farmer_id = _attribute(data, "farmerId", "farmer_id", "id")
    if not isinstance(farmer_id, str) or not farmer_id.strip():
        raise AgristackCardError("AgriStack card response missing farmerId")

    display_name = _attribute(data, "displayName", "farmerName", "name")
    if not isinstance(display_name, str) or not display_name.strip():
        raise AgristackCardError("AgriStack card response missing farmer name")

    state_lgd = _attribute(data, "stateLgdCode", "state_lgd_code", "stateCode")
    if not state_lgd:
        state_lgd = canonical_state_lgd_code(fallback_state) or fallback_state
    else:
        state_lgd = canonical_state_lgd_code(str(state_lgd)) or str(state_lgd).zfill(2)

    state_name = _attribute(data, "stateName", "state_name", "state") or fallback_state
    district_name = _attribute(data, "districtName", "district_name", "district")

    raw_aadhar = _attribute(data, "aadhar", "maskedAadhar", "uid") or "XXXXXXXX9999"
    masked = mask_aadhar(str(raw_aadhar))

    app_no = _attribute(data, "applicationNo", "application_no", "appId") or f"APP-{farmer_id}"
    gender = _attribute(data, "gender")
    dob_or_age = _attribute(data, "dob", "dobOrAge", "age")
    pdf_url = _attribute(data, "pdfDownloadUrl", "pdf_url", "cardPdf")
    qr_payload = _attribute(data, "qrCodePayload", "qr_code", "qrCode") or f"AGRISTACK:{state_lgd}:{farmer_id}"

    # Parse parcels
    raw_parcels = _attribute(data, "parcels", "landParcels") or []
    if not isinstance(raw_parcels, list):
        raise AgristackCardError("AgriStack card parcels were not a list")

    parcels: list[LandHolding] = []
    crops_set: set[str] = set()

    for raw in raw_parcels:
        if not isinstance(raw, dict):
            continue
        farm_id = _attribute(raw, "farmId", "farm_id")
        if not isinstance(farm_id, str):
            continue
        try:
            validated_farm_id = validate_farm_id(farm_id, state_lgd_code=state_lgd)
        except FarmIdError as exc:
            raise AgristackCardError("AgriStack card contains an invalid farm id") from exc

        area = _area(_attribute(raw, "areaHectares", "area"))
        crops = _crops(_attribute(raw, "crops") or [])
        for c in crops:
            crops_set.add(c.commodity)
        parcels.append(LandHolding(validated_farm_id, area, crops))

    return AgristackCardData(
        farmer_id=str(farmer_id).strip(),
        application_no=str(app_no).strip(),
        state_lgd_code=str(state_lgd).strip(),
        state_name=str(state_name).strip(),
        district_name=str(district_name).strip() if district_name else None,
        display_name=str(display_name).strip(),
        masked_aadhar=masked,
        gender=str(gender).strip() if gender else None,
        dob_or_age=str(dob_or_age).strip() if dob_or_age else None,
        card_status=str(status).upper(),
        pdf_download_url=str(pdf_url).strip() if pdf_url else None,
        qr_code_payload=str(qr_payload).strip(),
        parcels=parcels,
        crop_summary=sorted(crops_set),
        fetched_at=datetime.now(UTC),
    )


class AgristackCardClient:
    """HTTP client for fetching digitized farmer cards via GET /agristack/newcard.php."""

    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    async def fetch_card(
        self,
        *,
        api_key: str,
        aadhar: str,
        state: str,
    ) -> AgristackCardData:
        masked = mask_aadhar(aadhar)
        params = {
            "api_key": api_key,
            "aadhar": aadhar.strip(),
            "state": state.strip(),
        }
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/agristack/newcard.php",
                    params=params,
                    headers={"accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            raise AgristackCardError("AgriStack card request failed") from exc

        if response.status_code == 401 or response.status_code == 403:
            raise AgristackCardError("AgriStack API key is invalid or unauthorized")
        if response.status_code == 404:
            raise AgristackCardError(f"No farmer profile found for Aadhaar {masked} in {state}")
        if response.status_code >= 400:
            raise AgristackCardError(f"AgriStack server returned status {response.status_code}")

        try:
            body = response.json()
        except ValueError as exc:
            raise AgristackCardError("AgriStack card endpoint returned invalid JSON") from exc

        return parse_card_response(body, fallback_state=state)
