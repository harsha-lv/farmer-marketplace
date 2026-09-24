from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PledgeEligibilityRequest(BaseModel):
    lot_code: str = Field(min_length=1, max_length=32)
    custom_ltv_percent: Decimal | None = Field(default=None, ge=Decimal("0.1"), le=Decimal("0.9"))


class PledgeEligibilityResponse(BaseModel):
    lot_code: str
    warehouse_receipt_id: str
    commodity: str
    quantity_mt: Decimal
    modal_price_per_mt: int
    valuation_inr: int
    ltv_percent: Decimal
    max_loan_amount_inr: int
    indicative_interest_rate_bps: int


class PledgeLoanApplyRequest(BaseModel):
    lot_code: str = Field(min_length=1, max_length=32)
    requested_amount_inr: int = Field(gt=0)
    tenure_days: int = Field(default=90, ge=30, le=365)
    disbursement_mode: str = Field(default="BANK_TRANSFER", description="BANK_TRANSFER or ERUPI_VOUCHER")
    lender_name: str | None = Field(default=None, max_length=128)


class PledgeLoanResponse(BaseModel):
    loan_id: str
    warehouse_receipt_id: str
    lot_code: str
    farmer_id: str
    commodity: str
    quantity_mt: Decimal
    valuation_inr: int
    principal_amount_inr: int
    interest_rate_bps: int
    tenure_days: int
    lien_status: str
    loan_status: str
    lender_name: str
    disbursement_mode: str
    disbursement_ref: str | None
    applied_at: datetime
    disbursed_at: datetime | None
    due_date: datetime
    repaid_at: datetime | None
    total_repaid_inr: int | None
    current_accrued_interest_inr: int | None = None
    current_payoff_amount_inr: int | None = None

    @classmethod
    def from_model(
        cls,
        loan,
        current_accrued_interest_inr: int | None = None,
        current_payoff_amount_inr: int | None = None,
    ) -> "PledgeLoanResponse":
        return cls(
            loan_id=loan.loan_id,
            warehouse_receipt_id=loan.warehouse_receipt_id,
            lot_code=loan.lot_code,
            farmer_id=loan.farmer_id,
            commodity=loan.commodity,
            quantity_mt=loan.quantity_mt,
            valuation_inr=loan.valuation_inr,
            principal_amount_inr=loan.principal_amount_inr,
            interest_rate_bps=loan.interest_rate_bps,
            tenure_days=loan.tenure_days,
            lien_status=loan.lien_status,
            loan_status=loan.loan_status,
            lender_name=loan.lender_name,
            disbursement_mode=loan.disbursement_mode,
            disbursement_ref=loan.disbursement_ref,
            applied_at=loan.applied_at,
            disbursed_at=loan.disbursed_at,
            due_date=loan.due_date,
            repaid_at=loan.repaid_at,
            total_repaid_inr=loan.total_repaid_inr,
            current_accrued_interest_inr=current_accrued_interest_inr,
            current_payoff_amount_inr=current_payoff_amount_inr,
        )


class PledgeLoanDisburseRequest(BaseModel):
    disbursement_ref: str | None = Field(default=None, max_length=128)


class PledgeLoanRepayRequest(BaseModel):
    repaid_amount_inr: int | None = Field(default=None, gt=0)


class PledgeLoanRepayResponse(BaseModel):
    loan_id: str
    status: str
    principal_inr: int
    interest_inr: int
    total_repaid_inr: int
    lien_status: str
    message: str
