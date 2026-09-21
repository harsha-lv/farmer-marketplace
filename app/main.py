from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.exception_handlers import install_exception_handlers
from app.api.health import router as health_router
from app.api.router import api_router
from app.config import Settings, get_settings
from app.db.session import Database
from app.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        configure_logging(settings.log_level)
        yield
        await database.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        openapi_version="3.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    install_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
