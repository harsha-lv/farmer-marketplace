from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance.models import PledgeLoan


class PledgeFinanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_loan_id(self, loan_id: str) -> PledgeLoan | None:
        statement = select(PledgeLoan).where(PledgeLoan.loan_id == loan_id)
        return await self.session.scalar(statement)

    async def get_by_receipt_id(self, warehouse_receipt_id: str) -> PledgeLoan | None:
        statement = select(PledgeLoan).where(PledgeLoan.warehouse_receipt_id == warehouse_receipt_id)
        return await self.session.scalar(statement)

    async def get_by_lot_code(self, lot_code: str) -> PledgeLoan | None:
        statement = select(PledgeLoan).where(PledgeLoan.lot_code == lot_code)
        return await self.session.scalar(statement)

    async def list_by_farmer(self, farmer_id: str) -> list[PledgeLoan]:
        statement = (
            select(PledgeLoan)
            .where(PledgeLoan.farmer_id == farmer_id)
            .order_by(PledgeLoan.applied_at.desc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def create_pledge_loan(
        self,
        *,
        loan_id: str,
        warehouse_receipt_id: str,
        lot_code: str,
        farmer_id: str,
        commodity: str,
        quantity_mt: Decimal,
        valuation_inr: int,
        principal_amount_inr: int,
        interest_rate_bps: int,
        tenure_days: int,
        lender_name: str,
        disbursement_mode: str,
        due_date: datetime,
    ) -> PledgeLoan:
        now = datetime.now(UTC)
        loan = PledgeLoan(
            loan_id=loan_id,
            warehouse_receipt_id=warehouse_receipt_id,
            lot_code=lot_code,
            farmer_id=farmer_id,
            commodity=commodity,
            quantity_mt=quantity_mt,
            valuation_inr=valuation_inr,
            principal_amount_inr=principal_amount_inr,
            interest_rate_bps=interest_rate_bps,
            tenure_days=tenure_days,
            lien_status="LIEN_MARKED",
            loan_status="APPROVED",
            lender_name=lender_name,
            disbursement_mode=disbursement_mode,
            disbursement_ref=None,
            applied_at=now,
            disbursed_at=None,
            due_date=due_date,
            repaid_at=None,
            total_repaid_inr=None,
        )
        self.session.add(loan)
        await self.session.flush()
        return loan

    async def disburse(
        self,
        loan: PledgeLoan,
        *,
        disbursement_ref: str,
        disbursed_at: datetime | None = None,
    ) -> PledgeLoan:
        now = disbursed_at or datetime.now(UTC)
        loan.loan_status = "DISBURSED"
        loan.disbursement_ref = disbursement_ref
        loan.disbursed_at = now
        await self.session.flush()
        return loan

    async def repay(
        self,
        loan: PledgeLoan,
        *,
        repaid_amount_inr: int,
        repaid_at: datetime | None = None,
    ) -> PledgeLoan:
        now = repaid_at or datetime.now(UTC)
        loan.loan_status = "REPAID"
        loan.lien_status = "LIEN_RELEASED"
        loan.total_repaid_inr = repaid_amount_inr
        loan.repaid_at = now
        await self.session.flush()
        return loan
