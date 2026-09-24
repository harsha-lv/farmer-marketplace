from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class DeliveryConfirmationRequest(BaseModel):
    acceptance: bool = True
    remarks: str | None = Field(default=None, max_length=512)


class TradeContractResponse(BaseModel):
    contract_code: str
    transaction_id: str
    lot_code: str
    farmer_id: str
    buyer_name: str
    buyer_address: str
    buyer_phone: str | None
    delivery_gps: str
    quantity_mt: Decimal
    price_inr: int
    commission_inr: int
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, contract) -> "TradeContractResponse":
        return cls(
            contract_code=contract.contract_code,
            transaction_id=contract.transaction_id,
            lot_code=contract.lot_code,
            farmer_id=contract.farmer_id,
            buyer_name=contract.buyer_name,
            buyer_address=contract.buyer_address,
            buyer_phone=contract.buyer_phone,
            delivery_gps=contract.delivery_gps,
            quantity_mt=contract.quantity_mt,
            price_inr=contract.price_inr,
            commission_inr=contract.commission_inr,
            status=contract.status,
            created_at=contract.created_at,
            updated_at=contract.updated_at,
        )


class SettlementInitiateRequest(BaseModel):
    payout_mode: str = Field(default="ERUPI_VOUCHER", description="ERUPI_VOUCHER or BANK_TRANSFER")
    beneficiary_phone: str | None = Field(default=None, max_length=32)
    beneficiary_name: str | None = Field(default=None, max_length=256)


class ErupiVoucherResponse(BaseModel):
    voucher_code: str
    settlement_id: str
    transaction_id: str
    farmer_id: str
    beneficiary_phone: str
    beneficiary_name: str
    amount_inr: int
    purpose_code: str
    issuer: str
    qr_payload: str
    status: str
    expires_at: datetime
    created_at: datetime
    redeemed_at: datetime | None

    @classmethod
    def from_model(cls, voucher) -> "ErupiVoucherResponse":
        return cls(
            voucher_code=voucher.voucher_code,
            settlement_id=voucher.settlement_id,
            transaction_id=voucher.transaction_id,
            farmer_id=voucher.farmer_id,
            beneficiary_phone=voucher.beneficiary_phone,
            beneficiary_name=voucher.beneficiary_name,
            amount_inr=voucher.amount_inr,
            purpose_code=voucher.purpose_code,
            issuer=voucher.issuer,
            qr_payload=voucher.qr_payload,
            status=voucher.status,
            expires_at=voucher.expires_at,
            created_at=voucher.created_at,
            redeemed_at=voucher.redeemed_at,
        )


class SettlementResponse(BaseModel):
    settlement_id: str
    transaction_id: str
    farmer_id: str
    gross_amount_inr: int
    commission_inr: int
    tds_inr: int
    net_payout_inr: int
    payout_mode: str
    settlement_due_date: datetime
    status: str
    payout_ref: str | None
    created_at: datetime
    settled_at: datetime | None
    voucher: ErupiVoucherResponse | None = None

    @classmethod
    def from_model(cls, settlement, voucher=None) -> "SettlementResponse":
        return cls(
            settlement_id=settlement.settlement_id,
            transaction_id=settlement.transaction_id,
            farmer_id=settlement.farmer_id,
            gross_amount_inr=settlement.gross_amount_inr,
            commission_inr=settlement.commission_inr,
            tds_inr=settlement.tds_inr,
            net_payout_inr=settlement.net_payout_inr,
            payout_mode=settlement.payout_mode,
            settlement_due_date=settlement.settlement_due_date,
            status=settlement.status,
            payout_ref=settlement.payout_ref,
            created_at=settlement.created_at,
            settled_at=settlement.settled_at,
            voucher=ErupiVoucherResponse.from_model(voucher) if voucher else None,
        )


class VoucherRedeemRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=128)
    location: str | None = Field(default=None, max_length=128)


class VoucherRedeemResponse(BaseModel):
    voucher_code: str
    amount_inr: int
    status: str
    redeemed_at: datetime
    agent_id: str
    message: str


class ReconciliationSummaryResponse(BaseModel):
    total_trades: int
    total_gross_inr: int
    total_commission_inr: int
    total_tds_inr: int
    total_net_payout_inr: int
    payouts_by_mode: dict[str, int]
    counts_by_status: dict[str, int]

