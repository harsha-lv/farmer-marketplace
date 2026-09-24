from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.trades.models import ErupiVoucher, SettlementRecord, TradeContract


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

    async def update_fulfillment(
        self,
        contract: TradeContract,
        *,
        fulfillment_status: str,
        tracking_url: str | None = None,
        carrier_name: str | None = None,
    ) -> TradeContract:
        contract.fulfillment_status = fulfillment_status
        if tracking_url is not None:
            contract.tracking_url = tracking_url
        if carrier_name is not None:
            contract.carrier_name = carrier_name
        contract.updated_at = datetime.now(UTC)
        await self.session.flush()
        return contract


class SettlementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_transaction(self, transaction_id: str) -> SettlementRecord | None:
        statement = select(SettlementRecord).where(SettlementRecord.transaction_id == transaction_id)
        return await self.session.scalar(statement)

    async def get_by_settlement_id(self, settlement_id: str) -> SettlementRecord | None:
        statement = select(SettlementRecord).where(SettlementRecord.settlement_id == settlement_id)
        return await self.session.scalar(statement)

    async def create_settlement(
        self,
        *,
        settlement_id: str,
        transaction_id: str,
        farmer_id: str,
        gross_amount_inr: int,
        commission_inr: int,
        tds_inr: int,
        net_payout_inr: int,
        payout_mode: str,
        settlement_due_date: datetime,
        status: str = "PENDING",
        payout_ref: str | None = None,
    ) -> SettlementRecord:
        now = datetime.now(UTC)
        record = SettlementRecord(
            settlement_id=settlement_id,
            transaction_id=transaction_id,
            farmer_id=farmer_id,
            gross_amount_inr=gross_amount_inr,
            commission_inr=commission_inr,
            tds_inr=tds_inr,
            net_payout_inr=net_payout_inr,
            payout_mode=payout_mode,
            settlement_due_date=settlement_due_date,
            status=status,
            payout_ref=payout_ref,
            created_at=now,
            settled_at=now if status == "SETTLED" else None,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def create_erupi_voucher(
        self,
        *,
        voucher_code: str,
        settlement_id: str,
        transaction_id: str,
        farmer_id: str,
        beneficiary_phone: str,
        beneficiary_name: str,
        amount_inr: int,
        purpose_code: str,
        issuer: str,
        qr_payload: str,
        expires_at: datetime,
    ) -> ErupiVoucher:
        now = datetime.now(UTC)
        voucher = ErupiVoucher(
            voucher_code=voucher_code,
            settlement_id=settlement_id,
            transaction_id=transaction_id,
            farmer_id=farmer_id,
            beneficiary_phone=beneficiary_phone,
            beneficiary_name=beneficiary_name,
            amount_inr=amount_inr,
            purpose_code=purpose_code,
            issuer=issuer,
            qr_payload=qr_payload,
            status="ISSUED",
            expires_at=expires_at,
            created_at=now,
            redeemed_at=None,
        )
        self.session.add(voucher)
        await self.session.flush()
        return voucher

    async def get_erupi_voucher(self, voucher_code: str) -> ErupiVoucher | None:
        statement = select(ErupiVoucher).where(ErupiVoucher.voucher_code == voucher_code)
        return await self.session.scalar(statement)

    async def get_erupi_by_transaction(self, transaction_id: str) -> ErupiVoucher | None:
        statement = select(ErupiVoucher).where(ErupiVoucher.transaction_id == transaction_id)
        return await self.session.scalar(statement)

    async def redeem_erupi_voucher(self, voucher: ErupiVoucher) -> ErupiVoucher:
        voucher.status = "REDEEMED"
        voucher.redeemed_at = datetime.now(UTC)
        settlement = await self.get_by_settlement_id(voucher.settlement_id)
        if settlement is not None:
            settlement.status = "SETTLED"
            settlement.settled_at = voucher.redeemed_at
        await self.session.flush()
        return voucher

    async def list_settlements(self) -> list[SettlementRecord]:
        statement = select(SettlementRecord)
        result = await self.session.scalars(statement)
        return list(result.all())

