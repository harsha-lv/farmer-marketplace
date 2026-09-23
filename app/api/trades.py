from fastapi import APIRouter

from app.api.deps import SessionDep
from app.errors import AppError
from app.trades.repository import ContractRepository
from app.trades.schemas import DeliveryConfirmationRequest, TradeContractResponse

router = APIRouter(prefix="/trades", tags=["trades"])


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

    await session.commit()
    return TradeContractResponse.from_model(contract)
