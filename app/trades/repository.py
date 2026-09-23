from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.trades.models import TradeContract


class ContractRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_transaction(self, transaction_id: str) -> TradeContract | None:
        statement = select(TradeContract).where(TradeContract.transaction_id == transaction_id)
        return await self.session.scalar(statement)

    async def save_draft(
        self,
        *,
        transaction_id: str,
        lot_code: str,
        farmer_id: str,
        buyer_name: str,
        buyer_address: str,
        buyer_phone: str | None,
        delivery_gps: str,
        quantity_mt: Decimal,
        price_inr: int,
        commission_inr: int,
    ) -> TradeContract:
        now = datetime.now(UTC)
        existing = await self.get_by_transaction(transaction_id)
        if existing is None:
            existing = TradeContract(
                contract_code=f"TLC-{transaction_id}"[:160],
                transaction_id=transaction_id,
                status="draft",
                created_at=now,
                updated_at=now,
                lot_code=lot_code,
                farmer_id=farmer_id,
                buyer_name=buyer_name,
                buyer_address=buyer_address,
                buyer_phone=buyer_phone,
                delivery_gps=delivery_gps,
                quantity_mt=quantity_mt,
                price_inr=price_inr,
                commission_inr=commission_inr,
            )
            self.session.add(existing)
        else:
            existing.lot_code = lot_code
            existing.farmer_id = farmer_id
            existing.buyer_name = buyer_name
            existing.buyer_address = buyer_address
            existing.buyer_phone = buyer_phone
            existing.delivery_gps = delivery_gps
            existing.quantity_mt = quantity_mt
            existing.price_inr = price_inr
            existing.commission_inr = commission_inr
            existing.updated_at = now
        await self.session.flush()
        return existing

    async def confirm(self, contract: TradeContract) -> TradeContract:
        contract.status = "confirmed"
        contract.updated_at = datetime.now(UTC)
        await self.session.flush()
        return contract

    async def settle(self, contract: TradeContract) -> TradeContract:
        contract.status = "settled"
        contract.updated_at = datetime.now(UTC)
        await self.session.flush()
        return contract

    async def dispute(self, contract: TradeContract) -> TradeContract:
        contract.status = "disputed"
        contract.updated_at = datetime.now(UTC)
        await self.session.flush()
        return contract

    async def cancel(self, contract: TradeContract) -> TradeContract:
        contract.status = "cancelled"
        contract.updated_at = datetime.now(UTC)
        await self.session.flush()
        return contract
