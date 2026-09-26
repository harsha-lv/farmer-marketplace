import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.agristack import router as agristack_router
from app.api.beckn import router as beckn_router
from app.api.beckn_bap import router as beckn_bap_router
from app.api.consents import root_consent_router
from app.api.health import router as health_router
from app.api.router import api_router
from app.config import Settings, get_settings
from app.db.session import Database
from app.exceptions import register_exception_handlers
from app.middleware import (
    RequestIDMiddleware,
    configure_cors,
    setup_structured_logging,
)
from app.telemetry.metrics import PrometheusMetricsMiddleware, metrics_endpoint
from app.telemetry.otel import setup_opentelemetry

logger = logging.getLogger("app.main")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        # 1. Startup: Structured logging with JSON and PII redaction
        setup_structured_logging(settings.log_level)

        # 2. Alembic migration head verification gate (configurable flag)
        if settings.check_alembic_head:
            from app.db.alembic_gate import verify_database_at_alembic_head

            logger.info("Validating database schema is at Alembic head...")
            verify_database_at_alembic_head(settings.database_url)

        logger.info("Application starting - version %s", settings.app_version)

        # 3. OpenTelemetry: FastAPI, SQLAlchemy, Redis, aiokafka (no-op when env unset)
        setup_opentelemetry(app=app_instance, engine=database.engine.sync_engine)

        # 4. Cache initialization
        from app.cache.client import get_cache_client

        cache_client = get_cache_client(settings)
        await cache_client.initialize()

        # 5. In-process workers fallback (for local dev when RUN_WORKERS_INLINE=true)
        inline_tasks: list[asyncio.Task[None]] = []
        if settings.run_workers_inline:
            logger.info("RUN_WORKERS_INLINE=true: starting in-process background worker daemons...")
            from app.workers.beckn_rpc import main as beckn_rpc_main
            from app.workers.ingestion import main as ingestion_main
            from app.workers.outbox_relay import main as outbox_relay_main

            inline_tasks.append(asyncio.create_task(ingestion_main()))
            inline_tasks.append(asyncio.create_task(beckn_rpc_main()))
            inline_tasks.append(asyncio.create_task(outbox_relay_main()))

        yield

        # 6. Cancel and drain inline worker tasks if running
        for t in inline_tasks:
            t.cancel()
        if inline_tasks:
            import asyncio
            await asyncio.gather(*inline_tasks, return_exceptions=True)

        # 7. Shutdown: Drain requests, flush OTel traces, close pools
        logger.info("Application shutting down - closing connection pools and flushing telemetry")
        try:
            from opentelemetry import trace

            provider = trace.get_tracer_provider()
            if hasattr(provider, "shutdown"):
                provider.shutdown()
        except Exception:
            pass


        await cache_client.close()
        await database.dispose()
        logger.info("Application shutdown complete.")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        openapi_version="3.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database

    # Attach polished OpenAPI 3.1 schema generator
    from app.openapi import generate_custom_openapi
    app.openapi = lambda: generate_custom_openapi(app)

    # Register CORS middleware
    configure_cors(app)

    # Register RequestID ASGI middleware
    app.add_middleware(RequestIDMiddleware)

    # Register Prometheus Metrics Middleware
    app.add_middleware(PrometheusMetricsMiddleware)

    # Register Request Timeout Middleware
    from app.middleware.timeout import RequestTimeoutMiddleware
    app.add_middleware(
        RequestTimeoutMiddleware,
        timeout_seconds=settings.server_request_timeout_seconds,
    )

    # Register Security Middleware (Security Headers, Rate Limiting, Request Size Limiter)
    from app.cache.idempotency import IdempotencyMiddleware
    from app.middleware.audit import AuditLogMiddleware
    from app.middleware.csrf import CSRFDoubleSubmitMiddleware
    from app.middleware.security import SecurityMiddleware

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(SecurityMiddleware, max_body_size=settings.max_request_body_size_bytes)
    app.add_middleware(CSRFDoubleSubmitMiddleware)
    app.add_middleware(AuditLogMiddleware)

    # Register Global Exception Handlers
    register_exception_handlers(app)

    # Register Observability & Prometheus Endpoint
    app.add_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)

    # Register Routers
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(health_router)  # Also include at root for direct load balancer probes
    app.include_router(api_router)
    app.include_router(beckn_router)
    app.include_router(beckn_bap_router)
    from app.api.routers.logistics_webhooks import router as logistics_webhooks_router

    app.include_router(logistics_webhooks_router)
    app.include_router(agristack_router)
    app.include_router(root_consent_router)

    return app


app = create_app()
