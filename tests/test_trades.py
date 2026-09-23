from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.config import Settings
from app.db.session import Database
from app.main import create_app
from app.trades.models import TradeContract
from app.trades.repository import ContractRepository


def _make_contract(status: str = "confirmed") -> TradeContract:
    now = datetime.now(UTC)
    contract = TradeContract(
        contract_code="TLC-txn-trade-test",
        transaction_id="txn-trade-test",
        status=status,
        created_at=now,
        updated_at=now,
        lot_code="LOT-1",
        farmer_id="MH-400004",
        buyer_name="Buyer Co",
        buyer_address="Mumbai",
        buyer_phone="+919876543210",
        delivery_gps="19.0760,72.8777",
        quantity_mt=Decimal("2.5"),
        price_inr=55000,
        commission_inr=5000,
    )
    return contract


def test_get_trade_contract_returns_contract_details() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )

    class MockContractRepo:
        def __init__(self, session):
            pass

        async def get_by_transaction(self, transaction_id: str):
            if transaction_id == "txn-trade-test":
                return _make_contract("confirmed")
            return None

    import app.api.trades as trades_module

    orig_repo = trades_module.ContractRepository
    trades_module.ContractRepository = MockContractRepo
    try:
        with TestClient(application) as client:
            response = client.get("/api/v1/trades/txn-trade-test")

        assert response.status_code == 200
        data = response.json()
        assert data["transaction_id"] == "txn-trade-test"
        assert data["status"] == "confirmed"
        assert data["price_inr"] == 55000
    finally:
        trades_module.ContractRepository = orig_repo


def test_get_trade_contract_not_found() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )

    class MockContractRepo:
        def __init__(self, session):
            pass

        async def get_by_transaction(self, transaction_id: str):
            return None

    import app.api.trades as trades_module

    orig_repo = trades_module.ContractRepository
    trades_module.ContractRepository = MockContractRepo
    try:
        with TestClient(application) as client:
            response = client.get("/api/v1/trades/txn-unknown")

        assert response.status_code == 404
        assert response.json()["errors"][0]["title"] == "contract not found"
    finally:
        trades_module.ContractRepository = orig_repo


def test_confirm_delivery_settles_confirmed_contract() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )

    contract = _make_contract("confirmed")

    class MockContractRepo:
        def __init__(self, session):
            pass

        async def get_by_transaction(self, transaction_id: str):
            return contract if transaction_id == "txn-trade-test" else None

        async def settle(self, target):
            target.status = "settled"
            return target

    import app.api.trades as trades_module

    orig_repo = trades_module.ContractRepository
    trades_module.ContractRepository = MockContractRepo
    try:
        with TestClient(application) as client:
            response = client.post(
                "/api/v1/trades/txn-trade-test/delivery",
                json={"acceptance": True, "remarks": "Delivered in full"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "settled"
    finally:
        trades_module.ContractRepository = orig_repo


def test_rejecting_delivery_disputes_contract() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )

    contract = _make_contract("confirmed")

    class MockContractRepo:
        def __init__(self, session):
            pass

        async def get_by_transaction(self, transaction_id: str):
            return contract if transaction_id == "txn-trade-test" else None

        async def dispute(self, target):
            target.status = "disputed"
            return target

    import app.api.trades as trades_module

    orig_repo = trades_module.ContractRepository
    trades_module.ContractRepository = MockContractRepo
    try:
        with TestClient(application) as client:
            response = client.post(
                "/api/v1/trades/txn-trade-test/delivery",
                json={"acceptance": False, "remarks": "Damaged goods in transit"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disputed"
    finally:
        trades_module.ContractRepository = orig_repo


def test_cannot_deliver_unconfirmed_contract() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )

    contract = _make_contract("draft")

    class MockContractRepo:
        def __init__(self, session):
            pass

        async def get_by_transaction(self, transaction_id: str):
            return contract

    import app.api.trades as trades_module

    orig_repo = trades_module.ContractRepository
    trades_module.ContractRepository = MockContractRepo
    try:
        with TestClient(application) as client:
            response = client.post(
                "/api/v1/trades/txn-trade-test/delivery",
                json={"acceptance": True},
            )

        assert response.status_code == 400
        assert response.json()["errors"][0]["title"] == "invalid contract status"
    finally:
        trades_module.ContractRepository = orig_repo


async def test_database_settle_contract_persists() -> None:
    database = Database("postgresql+asyncpg://app:app@127.0.0.1:5432/app")
    try:
        if not await database.ping():
            pytest.skip("postgres is not available")
        async with database.session_factory() as session:
            repository = ContractRepository(session)
            contract = await repository.save_draft(
                transaction_id="txn-settle-db",
                lot_code="LOT-1",
                farmer_id="MH-400004",
                buyer_name="Buyer Co",
                buyer_address="Mumbai",
                buyer_phone=None,
                delivery_gps="19.0760,72.8777",
                quantity_mt=Decimal("2"),
                price_inr=44000,
                commission_inr=4000,
            )
            await repository.confirm(contract)
            await session.commit()
            assert contract.status == "confirmed"

            await repository.settle(contract)
            await session.commit()

            fetched = await repository.get_by_transaction("txn-settle-db")
            assert fetched is not None
            assert fetched.status == "settled"

            await session.execute(delete(TradeContract).where(TradeContract.transaction_id == "txn-settle-db"))
            await session.commit()
    finally:
        await database.dispose()
