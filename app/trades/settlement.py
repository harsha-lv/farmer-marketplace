import uuid
from datetime import datetime, timedelta
from typing import Any

PURPOSE_AGRI_SETTLEMENT = "AGRI_PRODUCE_SETTLEMENT"
DEFAULT_ISSUER = "ONDC-RSP-PARTNER-BANK"


def calculate_ondc_settlement_date(delivery_date: datetime) -> datetime:
    """
    ONDC RSP settlement cycle calculation for agricultural commodities:
    Payment cycle executes on the immediate Friday following the delivery date plus two days.
    """
    target = delivery_date + timedelta(days=2)
    # weekday(): Monday is 0 and Sunday is 6. Friday is 4.
    days_to_add = (4 - target.weekday()) % 7
    settlement_date = target + timedelta(days=days_to_add)
    return settlement_date.replace(hour=18, minute=0, second=0, microsecond=0)


def calculate_payout_breakdown(
    gross_inr: int,
    commission_inr: int,
    tds_rate_bps: int = 100,
) -> tuple[int, int]:
    """
    Calculate statutory TDS (Section 194-O) and net farmer payout.
    Returns (tds_inr, net_payout_inr).
    """
    tds_inr = int(round(gross_inr * (tds_rate_bps / 10000)))
    net_payout_inr = max(0, gross_inr - commission_inr - tds_inr)
    return tds_inr, net_payout_inr


def generate_erupi_voucher_code() -> str:
    """Generate cryptographically random e-RUPI voucher identifier."""
    token = uuid.uuid4().hex[:12].upper()
    return f"ERUPI-AGRI-{token}"


def generate_erupi_qr_payload(
    voucher_code: str,
    amount_inr: int,
    transaction_id: str,
    purpose_code: str = PURPOSE_AGRI_SETTLEMENT,
) -> str:
    """
    Generate NPCI-compliant e-RUPI UPI URI payload for offline scanning
    at rural input dealers, cooperatives, or bank branches.
    """
    return (
        f"upi://mandate?pa=rsp@ondcbank&pn=ONDC_RSP&am={amount_inr}&mam={amount_inr}"
        f"&cu=INR&purpose={purpose_code}&tid={voucher_code}&tr={transaction_id}"
    )


class NpciVoucherClient:
    """SSRF-hardened client for NPCI e-RUPI gateway and partner bank settlement verification."""

    def __init__(
        self,
        gateway_url: str = "https://npci.org.in/api/v1/erupi",
        transport: Any | None = None,
        allow_private: bool = False,
    ) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self._transport = transport
        self._allow_private = allow_private

    async def verify_voucher_status(self, voucher_code: str) -> dict[str, Any]:
        """Verify voucher redemption status with the NPCI/Partner Bank gateway."""
        from app.common.http_client import SafeAsyncClient

        endpoint = f"{self.gateway_url}/status/{voucher_code}"
        async with SafeAsyncClient(
            transport=self._transport,
            allow_private=self._allow_private,
        ) as client:
            resp = await client.get(endpoint)
            if resp.status_code == 200:
                return resp.json()
            return {"status": "ACTIVE", "voucher_code": voucher_code}
