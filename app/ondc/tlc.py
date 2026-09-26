"""Transaction-Level Contract (TLC) generation, signing, and verification.

Guarantees:
  - Generates immutable TLC on init
  - Embeds standard terms:
      - Settlement schedule: Friday + 2 banking days
      - Quality spec: grade, moisture, foreign matter tolerance
      - Quantity tolerance: +/- 2.0%
      - Penalty clauses: 0.5% per day delivery delay deduction
      - Dispute jurisdiction: State Agricultural Marketing Board Arbitration
  - HMAC-SHA256 signature and SHA-256 state hash
  - Stored immutably and referenced from TradeContract
"""

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.ondc.models import TlcRecord

logger = logging.getLogger("app.ondc.tlc")


def compute_friday_plus_two_settlement_date(reference_time: datetime | None = None) -> datetime:
    """Calculate 'Friday + 2' banking days settlement schedule.

    Finds the upcoming Friday, then adds 2 business days (Tuesday).
    """
    now = reference_time or datetime.now(UTC)
    # weekday(): Monday=0 ... Friday=4, Saturday=5, Sunday=6
    days_until_friday = (4 - now.weekday()) % 7
    if days_until_friday == 0 and now.hour >= 17:
        days_until_friday = 7
    friday = now + timedelta(days=days_until_friday)
    # Friday + 2 business days = Tuesday (+4 calendar days)
    settlement_date = friday + timedelta(days=4)
    return settlement_date.replace(hour=17, minute=0, second=0, microsecond=0)


def generate_tlc_terms(
    commodity: str,
    grade: str,
    quantity_mt: float,
    price_per_mt: int,
    commission_percent: int,
    buyer_name: str,
    farmer_id: str,
    delivery_location: str,
    chosen_lsp: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Assemble canonical TLC terms and conditions."""
    item_total = int(quantity_mt * price_per_mt)
    commission_val = int(item_total * (commission_percent / 100.0))
    total_val = item_total + commission_val
    settlement_due = compute_friday_plus_two_settlement_date()

    carrier_name = "Platform Default Carrier"
    lsp_id = None
    if isinstance(chosen_lsp, dict):
        carrier_name = chosen_lsp.get("lsp_name") or chosen_lsp.get("carrier_name") or "Network LSP"
        lsp_id = chosen_lsp.get("lsp_id")
    elif isinstance(chosen_lsp, str) and chosen_lsp.strip():
        carrier_name = chosen_lsp.strip()
        lsp_id = chosen_lsp.strip()

    delivery_terms_dict: dict[str, Any] = {
        "location": delivery_location,
        "carrier": carrier_name,
        "dispatch_sla_hours": 48,
        "inspection_window_hours": 24,
    }
    if lsp_id:
        delivery_terms_dict["lsp_id"] = lsp_id

    return {
        "contract_standard": "ONDC:AGR10:TLC:V2",
        "parties": {
            "seller_farmer_id": farmer_id,
            "buyer_name": buyer_name,
            "facilitator_fpo": "FPO Primary Market Desk",
        },
        "commodity_specification": {
            "commodity": commodity,
            "grade": grade,
            "max_moisture_percentage": 12.0,
            "max_foreign_matter_percentage": 1.5,
            "quantity_mt": quantity_mt,
            "quantity_tolerance_percentage": 2.0,  # +/- 2%
        },
        "financial_terms": {
            "currency": "INR",
            "item_total_inr": item_total,
            "commission_percent": commission_percent,
            "commission_inr": commission_val,
            "total_contract_inr": total_val,
            "settlement_schedule": "Friday + 2 Banking Days",
            "settlement_due_date": settlement_due.strftime("%Y-%m-%d"),
        },
        "delivery_terms": delivery_terms_dict,
        "clauses": {
            "delay_penalty_per_day_percent": 0.5,
            "max_delay_days": 5,
            "dispute_jurisdiction": "State Agricultural Marketing Board Arbitration Council",
            "law": "Indian Contract Act, 1872 & Farmers Empowerment and Protection Agreement Act",
        },
    }


def compute_tlc_hash(terms_dict: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of canonical TLC terms."""
    canonical_json = json.dumps(terms_dict, sort_keys=True, default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def sign_tlc_hmac(tlc_hash: str, secret_key: str) -> str:
    """Sign TLC hash using HMAC-SHA256."""
    return hmac.new(secret_key.encode("utf-8"), tlc_hash.encode("utf-8"), hashlib.sha256).hexdigest()


class TlcService:
    """Service generating, signing, and persisting Transaction-Level Contracts (TLC)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.secret_key = get_settings().jwt_secret_key

    async def generate_and_persist(
        self,
        transaction_id: str,
        contract_code: str,
        commodity: str,
        grade: str,
        quantity_mt: float,
        price_per_mt: int,
        commission_percent: int,
        buyer_name: str,
        farmer_id: str,
        delivery_location: str,
        chosen_lsp: dict[str, Any] | str | None = None,
    ) -> TlcRecord:
        """Create TLC on init, sign with HMAC-SHA256, and store immutably."""
        terms = generate_tlc_terms(
            commodity=commodity,
            grade=grade,
            quantity_mt=quantity_mt,
            price_per_mt=price_per_mt,
            commission_percent=commission_percent,
            buyer_name=buyer_name,
            farmer_id=farmer_id,
            delivery_location=delivery_location,
            chosen_lsp=chosen_lsp,
        )
        tlc_hash = compute_tlc_hash(terms)
        signature = sign_tlc_hmac(tlc_hash, self.secret_key)

        record = TlcRecord(
            contract_code=contract_code,
            transaction_id=transaction_id,
            tlc_hash=tlc_hash,
            tlc_terms_json=terms,
            signature=signature,
            created_at=datetime.now(UTC),
        )
        self.session.add(record)
        await self.session.commit()
        logger.info("Generated and signed immutable TLC %s for tx %s (hash=%s)", contract_code, transaction_id, tlc_hash)
        return record

    async def get_by_transaction(self, transaction_id: str) -> TlcRecord | None:
        stmt = select(TlcRecord).where(TlcRecord.transaction_id == transaction_id)
        return (await self.session.scalars(stmt)).first()

    def verify_tlc(self, record: TlcRecord) -> bool:
        """Verify integrity and signature of stored TLC."""
        expected_hash = compute_tlc_hash(record.tlc_terms_json)
        if expected_hash != record.tlc_hash:
            return False
        expected_sig = sign_tlc_hmac(record.tlc_hash, self.secret_key)
        return hmac.compare_digest(expected_sig, record.signature)
