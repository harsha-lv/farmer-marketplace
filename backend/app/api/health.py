from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.api.deps import DatabaseDep, SettingsDep

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


class ReadinessChecks(BaseModel):
    database: str


class ReadinessResponse(BaseModel):
    status: str
    checks: ReadinessChecks


@router.get("/health")
async def health(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/ready", responses={503: {"model": ReadinessResponse}})
async def ready(database: DatabaseDep, response: Response) -> ReadinessResponse:
    database_up = await database.ping()
    response.status_code = 200 if database_up else 503
    return ReadinessResponse(
        status="ok" if database_up else "unavailable",
        checks=ReadinessChecks(database="up" if database_up else "down"),
    )
