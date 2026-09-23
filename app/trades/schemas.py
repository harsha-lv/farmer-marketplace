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
