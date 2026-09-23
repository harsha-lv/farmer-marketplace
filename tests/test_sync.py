from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _make_lot():
    lot = type("Lot", (), {})()
    lot.lot_code = "LOT-SYNC-1"
    lot.farmer_id = "MH-400004"
    lot.commodity = "Wheat"
    lot.variety = "Sharbati"
    lot.quantity_mt = Decimal("15.0")
    lot.status = "registered"
    lot.enam_lot_id = "ENAM-100"
    lot.warehouse_receipt_id = None
    lot.created_at = datetime.now(UTC)
    lot.assay = type("Assay", (), {"grade": "FAQ"})()
    return lot


def test_sync_pull_returns_inventory_lots() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )

    class MockLotRepo:
        def __init__(self, session):
            pass

        async def list_modified_since(self, since):
            return [_make_lot()]

    import app.api.sync as sync_module

    orig_repo = sync_module.LotRepository
    sync_module.LotRepository = MockLotRepo
    try:
        with TestClient(application) as client:
            response = client.get("/api/v1/sync")

        assert response.status_code == 200
        data = response.json()
        assert "changes" in data
        assert "timestamp" in data
        lots = data["changes"]["inventory_lots"]["created"]
        assert len(lots) == 1
        assert lots[0]["id"] == "LOT-SYNC-1"
        assert lots[0]["commodity"] == "Wheat"
        assert lots[0]["quantity_mt"] == 15.0
    finally:
        sync_module.LotRepository = orig_repo


def test_sync_push_creates_and_resolves_conflicts() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
        )
    )

    existing_lot = _make_lot()

    class MockLotRepo:
        def __init__(self, session):
            self.created = []

        async def get(self, lot_code: str):
            if lot_code == "LOT-SYNC-1":
                return existing_lot
            return None

        async def create(self, request):
            new_lot = _make_lot()
            new_lot.lot_code = "LOT-NEW-1"
            self.created.append(new_lot)
            return new_lot

    import app.api.sync as sync_module

    orig_repo = sync_module.LotRepository
    sync_module.LotRepository = MockLotRepo
    try:
        with TestClient(application) as client:
            response = client.post(
                "/api/v1/sync",
                json={
                    "changes": {
                        "inventory_lots": {
                            "created": [
                                # Existing lot -> conflict resolution updates quantity
                                {
                                    "id": "LOT-SYNC-1",
                                    "farmer_id": "MH-400004",
                                    "commodity": "Wheat",
                                    "quantity_mt": 20.0,
                                },
                                # New lot -> creates record
                                {
                                    "id": "LOT-NEW-1",
                                    "farmer_id": "MH-400004",
                                    "consent_artifact_id": "art-1",
                                    "commodity": "Onion",
                                    "variety": "Red",
                                    "quantity_mt": 8.0,
                                    "grade": "FAQ",
                                },
                            ],
                            "updated": [],
                            "deleted": [],
                        }
                    },
                    "last_pulled_at": 1695321600,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["applied"]["created"] == 1
        assert data["applied"]["updated"] == 1
        assert existing_lot.quantity_mt == Decimal("20.0")
    finally:
        sync_module.LotRepository = orig_repo
