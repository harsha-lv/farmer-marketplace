from fastapi import APIRouter

from app.api.consents import router as consents_router
from app.api.farmers import router as farmers_router
from app.api.prices import router as prices_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(prices_router)
api_router.include_router(farmers_router)
api_router.include_router(consents_router)
