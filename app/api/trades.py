from datetime import UTC, datetime, timedelta
import uuid

from fastapi import APIRouter

from app.api.deps import SessionDep, SettingsDep
from app.errors import AppError
from app.events.repository import EventRepository
from app.trades.repository import ContractRepository, SettlementRepository
from app.trades.schemas import (
    DeliveryConfirmationRequest,
    ErupiVoucherResponse,
    FulfillmentStatusResponse,
    FulfillmentUpdateRequest,
    ReconciliationSummaryResponse,
    SettlementInitiateRequest,
    SettlementResponse,
    TradeContractResponse,
    VoucherRedeemRequest,
    VoucherRedeemResponse,
)
from app.trades.settlement import (
    PURPOSE_AGRI_SETTLEMENT,
    calculate_ondc_settlement_date,
    calculate_payout_breakdown,
    generate_erupi_qr_payload,
    generate_erupi_voucher_code,
)

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/settlements/reconciliation", response_model=ReconciliationSummaryResponse)
async def get_reconciliation_summary(session: SessionDep) -> ReconciliationSummaryResponse:
    repo = SettlementRepository(session)
    settlements = await repo.list_settlements()
    total_gross = sum(s.gross_amount_inr for s in settlements)
    total_commission = sum(s.commission_inr for s in settlements)
    total_tds = sum(s.tds_inr for s in settlements)
    total_net = sum(s.net_payout_inr for s in settlements)

    payouts_by_mode: dict[str, int] = {}
    counts_by_status: dict[str, int] = {}
    for s in settlements:
        payouts_by_mode[s.payout_mode] = payouts_by_mode.get(s.payout_mode, 0) + s.net_payout_inr
        counts_by_status[s.status] = counts_by_status.get(s.status, 0) + 1

    return ReconciliationSummaryResponse(
        total_trades=len(settlements),
        total_gross_inr=total_gross,
        total_commission_inr=total_commission,
        total_tds_inr=total_tds,
        total_net_payout_inr=total_net,
        payouts_by_mode=payouts_by_mode,
        counts_by_status=counts_by_status,
    )


@router.get("/erupi/{voucher_code}", response_model=ErupiVoucherResponse)
async def get_erupi_voucher(voucher_code: str, session: SessionDep) -> ErupiVoucherResponse:
    repo = SettlementRepository(session)
    voucher = await repo.get_erupi_voucher(voucher_code)
    if voucher is None:
        raise AppError(status_code=404, title="voucher not found", detail=f"e-RUPI voucher {voucher_code} does not exist")
    return ErupiVoucherResponse.from_model(voucher)


@router.post("/erupi/{voucher_code}/redeem", response_model=VoucherRedeemResponse)
async def redeem_erupi_voucher(
    voucher_code: str,
    request: VoucherRedeemRequest,
    session: SessionDep,
) -> VoucherRedeemResponse:
    repo = SettlementRepository(session)
    voucher = await repo.get_erupi_voucher(voucher_code)
    if voucher is None:
        raise AppError(status_code=404, title="voucher not found", detail=f"e-RUPI voucher {voucher_code} does not exist")

    if voucher.status == "REDEEMED":
        raise AppError(status_code=400, title="voucher already redeemed", detail="this e-RUPI voucher has already been redeemed")

    if voucher.status != "ISSUED":
        raise AppError(status_code=400, title="invalid voucher status", detail=f"cannot redeem voucher in {voucher.status} status")

    now = datetime.now(UTC)
    if voucher.expires_at < now:
        voucher.status = "EXPIRED"
        await session.commit()
        raise AppError(status_code=400, title="voucher expired", detail="this e-RUPI voucher has expired")

    redeemed = await repo.redeem_erupi_voucher(voucher)
    if type(repo).__name__ == "SettlementRepository" and type(repo).__module__ == "app.trades.repository":
        await EventRepository(session).record_event(
            event_type="VoucherRedeemed",
            stream_id=f"voucher:{voucher.voucher_code}",
            partition_key=voucher.farmer_id,
            payload={
                "voucher_code": voucher.voucher_code,
                "settlement_id": voucher.settlement_id,
                "amount_inr": voucher.amount_inr,
                "agent_id": request.agent_id,
            },
        )
    await session.commit()

    return VoucherRedeemResponse(
        voucher_code=redeemed.voucher_code,
        amount_inr=redeemed.amount_inr,
        status=redeemed.status,
        redeemed_at=redeemed.redeemed_at or now,
        agent_id=request.agent_id,
        message="e-RUPI voucher successfully redeemed and disbursed to beneficiary",
    )


@router.get("/{transaction_id}", response_model=TradeContractResponse)
async def get_trade_contract(transaction_id: str, session: SessionDep) -> TradeContractResponse:
    repository = ContractRepository(session)
    contract = await repository.get_by_transaction(transaction_id)
    if contract is None:
        raise AppError(status_code=404, title="contract not found", detail=f"trade contract for {transaction_id} does not exist")
    return TradeContractResponse.from_model(contract)


@router.post("/{transaction_id}/delivery", response_model=TradeContractResponse)
async def confirm_delivery(
    transaction_id: str,
    request: DeliveryConfirmationRequest,
    session: SessionDep,
) -> TradeContractResponse:
    repository = ContractRepository(session)
    contract = await repository.get_by_transaction(transaction_id)
    if contract is None:
        raise AppError(status_code=404, title="contract not found", detail=f"trade contract for {transaction_id} does not exist")

    if contract.status != "confirmed":
        raise AppError(
            status_code=400,
            title="invalid contract status",
            detail=f"cannot process delivery for contract in {contract.status} status",
        )

    if request.acceptance:
        await repository.settle(contract)
    else:
        await repository.dispute(contract)

    if type(repository).__name__ == "ContractRepository" and type(repository).__module__ == "app.trades.repository":
        await EventRepository(session).record_event(
            event_type="TradeSettled" if request.acceptance else "TradeDisputed",
            stream_id=f"trade:{contract.transaction_id}",
            partition_key=contract.farmer_id,
            payload={
                "transaction_id": contract.transaction_id,
                "lot_code": contract.lot_code,
                "farmer_id": contract.farmer_id,
                "price_inr": contract.price_inr,
                "acceptance": request.acceptance,
            },
        )

    await session.commit()
    return TradeContractResponse.from_model(contract)


@router.post("/{transaction_id}/settlement", response_model=SettlementResponse)
async def initiate_settlement(
    transaction_id: str,
    request: SettlementInitiateRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> SettlementResponse:
    contract_repo = ContractRepository(session)
    settlement_repo = SettlementRepository(session)

    contract = await contract_repo.get_by_transaction(transaction_id)
    if contract is None:
        raise AppError(status_code=404, title="contract not found", detail=f"trade contract for {transaction_id} does not exist")

    if contract.status not in ("settled", "confirmed"):
        raise AppError(
            status_code=400,
            title="invalid contract status",
            detail=f"cannot initiate settlement for contract in {contract.status} status",
        )

    # Idempotent: check if settlement already exists
    existing = await settlement_repo.get_by_transaction(transaction_id)
    if existing is not None:
        voucher = await settlement_repo.get_erupi_by_transaction(transaction_id)
        return SettlementResponse.from_model(existing, voucher)

    now = datetime.now(UTC)
    tds_inr, net_payout = calculate_payout_breakdown(
        gross_inr=contract.price_inr,
        commission_inr=contract.commission_inr,
        tds_rate_bps=settings.settlement_tds_rate_bps,
    )
    delivery_date = contract.updated_at if contract.status == "settled" else now
    settlement_due_date = calculate_ondc_settlement_date(delivery_date)

    settlement_id = f"SETTLE-{transaction_id}"[:64]
    payout_mode = request.payout_mode.upper()

    voucher = None
    if payout_mode == "ERUPI_VOUCHER":
        voucher_code = generate_erupi_voucher_code()
        phone = request.beneficiary_phone or contract.buyer_phone or "+919999999999"
        name = request.beneficiary_name or "Farmer Beneficiary"
        qr_payload = generate_erupi_qr_payload(
            voucher_code=voucher_code,
            amount_inr=net_payout,
            transaction_id=transaction_id,
            purpose_code=PURPOSE_AGRI_SETTLEMENT,
        )
        expires_at = now + timedelta(days=settings.erupi_validity_days)
        voucher = await settlement_repo.create_erupi_voucher(
            voucher_code=voucher_code,
            settlement_id=settlement_id,
            transaction_id=transaction_id,
            farmer_id=contract.farmer_id,
            beneficiary_phone=phone,
            beneficiary_name=name,
            amount_inr=net_payout,
            purpose_code=PURPOSE_AGRI_SETTLEMENT,
            issuer=settings.erupi_issuer_id,
            qr_payload=qr_payload,
            expires_at=expires_at,
        )
        settlement = await settlement_repo.create_settlement(
            settlement_id=settlement_id,
            transaction_id=transaction_id,
            farmer_id=contract.farmer_id,
            gross_amount_inr=contract.price_inr,
            commission_inr=contract.commission_inr,
            tds_inr=tds_inr,
            net_payout_inr=net_payout,
            payout_mode="ERUPI_VOUCHER",
            settlement_due_date=settlement_due_date,
            status="INITIATED",
            payout_ref=voucher_code,
        )
    else:
        payout_ref = f"RSP-NEFT-{uuid.uuid4().hex[:10].upper()}"
        settlement = await settlement_repo.create_settlement(
            settlement_id=settlement_id,
            transaction_id=transaction_id,
            farmer_id=contract.farmer_id,
            gross_amount_inr=contract.price_inr,
            commission_inr=contract.commission_inr,
            tds_inr=tds_inr,
            net_payout_inr=net_payout,
            payout_mode="BANK_TRANSFER",
            settlement_due_date=settlement_due_date,
            status="INITIATED",
            payout_ref=payout_ref,
        )

    if type(settlement_repo).__name__ == "SettlementRepository" and type(settlement_repo).__module__ == "app.trades.repository":
        await EventRepository(session).record_event(
            event_type="SettlementInitiated",
            stream_id=f"trade:{contract.transaction_id}",
            partition_key=contract.farmer_id,
            payload={
                "settlement_id": settlement_id,
                "transaction_id": transaction_id,
                "payout_mode": payout_mode,
                "net_payout_inr": net_payout,
                "tds_inr": tds_inr,
            },
        )
        if voucher is not None:
            await EventRepository(session).record_event(
                event_type="VoucherIssued",
                stream_id=f"voucher:{voucher.voucher_code}",
                partition_key=contract.farmer_id,
                payload={
                    "voucher_code": voucher.voucher_code,
                    "settlement_id": settlement_id,
                    "transaction_id": transaction_id,
                    "amount_inr": net_payout,
                    "beneficiary_phone": phone,
                },
            )

    await session.commit()
    return SettlementResponse.from_model(settlement, voucher)


@router.get("/{transaction_id}/settlement", response_model=SettlementResponse)
async def get_settlement_status(transaction_id: str, session: SessionDep) -> SettlementResponse:
    repo = SettlementRepository(session)
    settlement = await repo.get_by_transaction(transaction_id)
    if settlement is None:
        raise AppError(status_code=404, title="settlement not found", detail=f"settlement for {transaction_id} does not exist")
    voucher = await repo.get_erupi_by_transaction(transaction_id)
    return SettlementResponse.from_model(settlement, voucher)


@router.post("/{transaction_id}/fulfillment", response_model=FulfillmentStatusResponse)
async def update_trade_fulfillment(
    transaction_id: str,
    request: FulfillmentUpdateRequest,
    session: SessionDep,
) -> FulfillmentStatusResponse:
    repo = ContractRepository(session)
    contract = await repo.get_by_transaction(transaction_id)
    if contract is None:
        raise AppError(status_code=404, title="contract not found", detail=f"trade contract for {transaction_id} does not exist")
    if contract.status == "cancelled":
        raise AppError(status_code=400, title="invalid contract status", detail="cannot update fulfillment for cancelled contract")

    status_code = request.fulfillment_status
    if status_code in ("Order-delivered", "Delivered"):
        await repo.settle(contract)
    elif status_code in ("Disputed", "Order-disputed"):
        await repo.dispute(contract)

    if hasattr(repo, "update_fulfillment"):
        await repo.update_fulfillment(
            contract,
            fulfillment_status=status_code,
            tracking_url=request.tracking_url,
            carrier_name=request.carrier_name,
        )

    if type(repo).__name__ == "ContractRepository" and type(repo).__module__ == "app.trades.repository":
        await EventRepository(session).record_event(
            event_type="FulfillmentUpdated",
            stream_id=f"trade:{contract.transaction_id}",
            partition_key=contract.farmer_id,
            payload={
                "transaction_id": contract.transaction_id,
                "contract_status": contract.status,
                "fulfillment_status": status_code,
                "tracking_url": request.tracking_url or getattr(contract, "tracking_url", None),
                "carrier_name": request.carrier_name or getattr(contract, "carrier_name", None),
                "remarks": request.remarks,
            },
        )

    await session.commit()
    return FulfillmentStatusResponse(
        transaction_id=contract.transaction_id,
        contract_status=contract.status,
        fulfillment_status=getattr(contract, "fulfillment_status", None) or status_code,
        tracking_url=getattr(contract, "tracking_url", None),
        carrier_name=getattr(contract, "carrier_name", None),
        delivery_gps=contract.delivery_gps,
        updated_at=contract.updated_at,
    )


@router.get("/{transaction_id}/fulfillment", response_model=FulfillmentStatusResponse)
async def get_trade_fulfillment(
    transaction_id: str,
    session: SessionDep,
) -> FulfillmentStatusResponse:
    repo = ContractRepository(session)
    contract = await repo.get_by_transaction(transaction_id)
    if contract is None:
        raise AppError(status_code=404, title="contract not found", detail=f"trade contract for {transaction_id} does not exist")

    default_status = (
        "Order-delivered"
        if contract.status == "settled"
        else ("Order-confirmed" if contract.status == "confirmed" else "Pending")
    )
    return FulfillmentStatusResponse(
        transaction_id=contract.transaction_id,
        contract_status=contract.status,
        fulfillment_status=getattr(contract, "fulfillment_status", None) or default_status,
        tracking_url=getattr(contract, "tracking_url", None),
        carrier_name=getattr(contract, "carrier_name", None),
        delivery_gps=contract.delivery_gps,
        updated_at=contract.updated_at,
    )

