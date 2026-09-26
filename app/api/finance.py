import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends

from app.api.deps import (
    SessionDep,
    SettingsDep,
    get_current_user,
    require_org_access,
    require_roles,
)
from app.errors import AppError
from app.events.repository import EventRepository
from app.finance.calculator import (
    calculate_pledge_eligibility,
    calculate_total_payoff,
)
from app.finance.repository import PledgeFinanceRepository
from app.finance.schemas import (
    PledgeEligibilityRequest,
    PledgeEligibilityResponse,
    PledgeLoanApplyRequest,
    PledgeLoanDisburseRequest,
    PledgeLoanRepayRequest,
    PledgeLoanRepayResponse,
    PledgeLoanResponse,
)
from app.lots.repository import LotRepository
from app.prices.repository import PriceRepository
from app.prices.schemas import PriceFilter

router = APIRouter(
    prefix="/finance",
    tags=["finance"],
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles("farmer", "fpo_operator", "bank", "admin")),
        Depends(require_org_access("fpo_id")),
    ],
)

DEFAULT_FALLBACK_PRICE_PER_MT = 25000  # Rs 2,500/quintal default


async def _resolve_modal_price_per_mt(lot, price_repo: PriceRepository) -> int:
    query = PriceFilter(commodity=lot.commodity, limit=1)
    page = await price_repo.list_prices(query)
    if page.records:
        return page.records[0].modal_price_inr_per_quintal * 10
    return DEFAULT_FALLBACK_PRICE_PER_MT


@router.post("/pledge/eligibility", response_model=PledgeEligibilityResponse)
async def check_pledge_eligibility(
    request: PledgeEligibilityRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> PledgeEligibilityResponse:
    lot_repo = LotRepository(session)
    lot = await lot_repo.get(request.lot_code)
    if lot is None:
        raise AppError(status_code=404, title="lot not found", detail=f"lot with code {request.lot_code} does not exist")

    if not lot.warehouse_receipt_id:
        raise AppError(
            status_code=400,
            title="lot not warehoused",
            detail="cannot compute pledge finance eligibility for lot without electronic Negotiable Warehouse Receipt (eNWR)",
        )

    price_repo = PriceRepository(session)
    modal_price_per_mt = await _resolve_modal_price_per_mt(lot, price_repo)
    ltv = (
        request.custom_ltv_percent
        if request.custom_ltv_percent is not None
        else (Decimal(settings.pledge_finance_default_ltv_bps) / Decimal(10000))
    )

    valuation_inr, max_loan_inr = calculate_pledge_eligibility(
        quantity_mt=lot.quantity_mt,
        modal_price_per_mt=modal_price_per_mt,
        ltv_ratio=ltv,
    )

    return PledgeEligibilityResponse(
        lot_code=lot.lot_code,
        warehouse_receipt_id=lot.warehouse_receipt_id,
        commodity=lot.commodity,
        quantity_mt=lot.quantity_mt,
        modal_price_per_mt=modal_price_per_mt,
        valuation_inr=valuation_inr,
        ltv_percent=ltv * Decimal(100),
        max_loan_amount_inr=max_loan_inr,
        indicative_interest_rate_bps=settings.pledge_finance_default_interest_bps,
    )


@router.post("/pledge/apply", response_model=PledgeLoanResponse)
async def apply_pledge_loan(
    request: PledgeLoanApplyRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> PledgeLoanResponse:
    lot_repo = LotRepository(session)
    lot = await lot_repo.get(request.lot_code)
    if lot is None:
        raise AppError(status_code=404, title="lot not found", detail=f"lot with code {request.lot_code} does not exist")

    if not lot.warehouse_receipt_id:
        raise AppError(
            status_code=400,
            title="lot not warehoused",
            detail="pledge loan requires an accredited electronic Negotiable Warehouse Receipt (eNWR)",
        )

    finance_repo = PledgeFinanceRepository(session)
    existing = await finance_repo.get_by_receipt_id(lot.warehouse_receipt_id)
    if existing is not None and existing.loan_status != "REPAID":
        raise AppError(
            status_code=409,
            title="lien already marked",
            detail="an active pledge loan or lien already exists on this warehouse receipt",
        )

    price_repo = PriceRepository(session)
    modal_price_per_mt = await _resolve_modal_price_per_mt(lot, price_repo)
    ltv = Decimal(settings.pledge_finance_default_ltv_bps) / Decimal(10000)
    valuation_inr, max_loan_inr = calculate_pledge_eligibility(
        quantity_mt=lot.quantity_mt,
        modal_price_per_mt=modal_price_per_mt,
        ltv_ratio=ltv,
    )

    if request.requested_amount_inr > max_loan_inr:
        raise AppError(
            status_code=400,
            title="amount exceeds eligible limit",
            detail=f"requested amount {request.requested_amount_inr} INR exceeds maximum eligible borrowing limit of {max_loan_inr} INR",
        )

    now = datetime.now(UTC)
    loan_id = f"LOAN-ENWR-{uuid.uuid4().hex[:10].upper()}"
    due_date = now + timedelta(days=request.tenure_days)
    lender = request.lender_name or settings.pledge_finance_default_lender
    interest_bps = settings.pledge_finance_default_interest_bps

    loan = await finance_repo.create_pledge_loan(
        loan_id=loan_id,
        warehouse_receipt_id=lot.warehouse_receipt_id,
        lot_code=lot.lot_code,
        farmer_id=lot.farmer_id,
        commodity=lot.commodity,
        quantity_mt=lot.quantity_mt,
        valuation_inr=valuation_inr,
        principal_amount_inr=request.requested_amount_inr,
        interest_rate_bps=interest_bps,
        tenure_days=request.tenure_days,
        lender_name=lender,
        disbursement_mode=request.disbursement_mode.upper(),
        due_date=due_date,
    )

    if type(finance_repo).__name__ == "PledgeFinanceRepository" and type(finance_repo).__module__ == "app.finance.repository":
        event_repo = EventRepository(session)
        await event_repo.record_event(
            event_type="PledgeLoanApplied",
            stream_id=f"loan:{loan.loan_id}",
            partition_key=loan.farmer_id,
            payload={
                "loan_id": loan.loan_id,
                "warehouse_receipt_id": loan.warehouse_receipt_id,
                "lot_code": loan.lot_code,
                "farmer_id": loan.farmer_id,
                "principal_amount_inr": loan.principal_amount_inr,
                "valuation_inr": loan.valuation_inr,
                "lender_name": loan.lender_name,
            },
        )
        await event_repo.record_event(
            event_type="LienMarked",
            stream_id=f"receipt:{loan.warehouse_receipt_id}",
            partition_key=loan.farmer_id,
            payload={
                "warehouse_receipt_id": loan.warehouse_receipt_id,
                "lot_code": loan.lot_code,
                "loan_id": loan.loan_id,
                "lien_status": "LIEN_MARKED",
            },
        )

    await session.commit()
    return PledgeLoanResponse.from_model(loan)


@router.post(
    "/pledge/{loan_id}/disburse",
    response_model=PledgeLoanResponse,
    dependencies=[Depends(require_roles("bank", "admin"))],
)
async def disburse_pledge_loan(
    loan_id: str,
    request: PledgeLoanDisburseRequest,
    session: SessionDep,
) -> PledgeLoanResponse:
    finance_repo = PledgeFinanceRepository(session)
    loan = await finance_repo.get_by_loan_id(loan_id)
    if loan is None:
        raise AppError(status_code=404, title="loan not found", detail=f"pledge loan {loan_id} does not exist")

    if loan.loan_status != "APPROVED":
        raise AppError(
            status_code=400,
            title="invalid loan status",
            detail=f"cannot disburse pledge loan in {loan.loan_status} status",
        )

    now = datetime.now(UTC)
    if loan.disbursement_mode == "ERUPI_VOUCHER":
        disbursement_ref = request.disbursement_ref or f"ERUPI-LOAN-{uuid.uuid4().hex[:10].upper()}"
    else:
        disbursement_ref = request.disbursement_ref or f"NEFT-AGRI-{uuid.uuid4().hex[:10].upper()}"

    await finance_repo.disburse(loan, disbursement_ref=disbursement_ref, disbursed_at=now)

    if type(finance_repo).__name__ == "PledgeFinanceRepository" and type(finance_repo).__module__ == "app.finance.repository":
        await EventRepository(session).record_event(
            event_type="PledgeLoanDisbursed",
            stream_id=f"loan:{loan.loan_id}",
            partition_key=loan.farmer_id,
            payload={
                "loan_id": loan.loan_id,
                "warehouse_receipt_id": loan.warehouse_receipt_id,
                "disbursed_amount_inr": loan.principal_amount_inr,
                "disbursement_mode": loan.disbursement_mode,
                "disbursement_ref": disbursement_ref,
            },
        )

    await session.commit()
    return PledgeLoanResponse.from_model(loan)


@router.post("/pledge/{loan_id}/repay", response_model=PledgeLoanRepayResponse)
async def repay_pledge_loan(
    loan_id: str,
    request: PledgeLoanRepayRequest,
    session: SessionDep,
) -> PledgeLoanRepayResponse:
    finance_repo = PledgeFinanceRepository(session)
    loan = await finance_repo.get_by_loan_id(loan_id)
    if loan is None:
        raise AppError(status_code=404, title="loan not found", detail=f"pledge loan {loan_id} does not exist")

    if loan.loan_status != "DISBURSED":
        raise AppError(
            status_code=400,
            title="invalid loan status",
            detail=f"cannot repay pledge loan in {loan.loan_status} status",
        )

    now = datetime.now(UTC)
    disbursed_time = loan.disbursed_at or loan.applied_at
    days_elapsed = max(1, (now - disbursed_time).days)
    interest_inr, total_payoff = calculate_total_payoff(
        principal_inr=loan.principal_amount_inr,
        interest_rate_bps=loan.interest_rate_bps,
        days_elapsed=days_elapsed,
    )

    repaid_amount = request.repaid_amount_inr or total_payoff
    await finance_repo.repay(loan, repaid_amount_inr=repaid_amount, repaid_at=now)

    if type(finance_repo).__name__ == "PledgeFinanceRepository" and type(finance_repo).__module__ == "app.finance.repository":
        event_repo = EventRepository(session)
        await event_repo.record_event(
            event_type="PledgeLoanRepaid",
            stream_id=f"loan:{loan.loan_id}",
            partition_key=loan.farmer_id,
            payload={
                "loan_id": loan.loan_id,
                "warehouse_receipt_id": loan.warehouse_receipt_id,
                "principal_inr": loan.principal_amount_inr,
                "interest_inr": interest_inr,
                "total_repaid_inr": repaid_amount,
            },
        )
        await event_repo.record_event(
            event_type="LienReleased",
            stream_id=f"receipt:{loan.warehouse_receipt_id}",
            partition_key=loan.farmer_id,
            payload={
                "warehouse_receipt_id": loan.warehouse_receipt_id,
                "loan_id": loan.loan_id,
                "lien_status": "LIEN_RELEASED",
            },
        )

    await session.commit()
    return PledgeLoanRepayResponse(
        loan_id=loan.loan_id,
        status="REPAID",
        principal_inr=loan.principal_amount_inr,
        interest_inr=interest_inr,
        total_repaid_inr=repaid_amount,
        lien_status="LIEN_RELEASED",
        message="Pledge loan successfully settled and warehouse receipt lien released",
    )


@router.get("/pledge/{loan_id}", response_model=PledgeLoanResponse)
async def get_pledge_loan(
    loan_id: str,
    session: SessionDep,
) -> PledgeLoanResponse:
    finance_repo = PledgeFinanceRepository(session)
    loan = await finance_repo.get_by_loan_id(loan_id)
    if loan is None:
        raise AppError(status_code=404, title="loan not found", detail=f"pledge loan {loan_id} does not exist")

    accrued_interest = None
    payoff_amount = None
    if loan.loan_status == "DISBURSED":
        now = datetime.now(UTC)
        disbursed_time = loan.disbursed_at or loan.applied_at
        days_elapsed = max(1, (now - disbursed_time).days)
        accrued_interest, payoff_amount = calculate_total_payoff(
            principal_inr=loan.principal_amount_inr,
            interest_rate_bps=loan.interest_rate_bps,
            days_elapsed=days_elapsed,
        )

    return PledgeLoanResponse.from_model(
        loan,
        current_accrued_interest_inr=accrued_interest,
        current_payoff_amount_inr=payoff_amount,
    )


@router.get("/pledge/farmer/{farmer_id}", response_model=list[PledgeLoanResponse])
async def list_farmer_pledge_loans(
    farmer_id: str,
    session: SessionDep,
) -> list[PledgeLoanResponse]:
    finance_repo = PledgeFinanceRepository(session)
    loans = await finance_repo.list_by_farmer(farmer_id)
    return [PledgeLoanResponse.from_model(loan) for loan in loans]
