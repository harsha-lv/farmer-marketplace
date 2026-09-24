from fastapi import APIRouter

from app.api.consents import router as consents_router
from app.api.events import router as events_router
from app.api.farmers import router as farmers_router
from app.api.finance import router as finance_router
from app.api.lots import router as lots_router
from app.api.prices import router as prices_router
from app.api.telemetry import router as telemetry_router
from app.api.trades import router as trades_router
from app.api.sync import router as sync_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(prices_router)
api_router.include_router(farmers_router)
api_router.include_router(consents_router)
api_router.include_router(lots_router)
api_router.include_router(trades_router)
api_router.include_router(sync_router)
api_router.include_router(events_router)
api_router.include_router(finance_router)
api_router.include_router(telemetry_router)
