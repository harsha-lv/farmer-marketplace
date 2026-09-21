from fastapi import APIRouter

from app.api.prices import router as prices_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(prices_router)
