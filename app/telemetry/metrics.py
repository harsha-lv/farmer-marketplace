"""Prometheus metrics definitions, middleware, and registry.

Exposes standard Prometheus metrics covering:
- http_request_duration_seconds histogram by route/status
- http_request_errors_total error rate
- kafka_consumer_lag
- outbox_relay_lag_seconds + outbox_unprocessed_count
- nats_ack_pending
- redis_cache_hits_total / redis_cache_misses_total (hit/miss ratio)
- db_pool_connections_in_use / db_pool_connections_idle
- assay_inference_latency_seconds by model/architecture
- sync_push_conflicts_total by table
- consent_revocations_total
"""

import ipaddress
import logging
import os
import re
import time

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("app.telemetry.metrics")

# ============================================================================
# Metric Definitions
# ============================================================================

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route", "status_code"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "route", "status_code"],
)

HTTP_REQUEST_ERRORS_TOTAL = Counter(
    "http_request_errors_total",
    "Total HTTP request errors by type and route",
    ["type", "route"],
)

KAFKA_CONSUMER_LAG = Gauge(
    "kafka_consumer_lag",
    "Kafka consumer lag in messages behind partition high watermark",
    ["topic", "partition", "consumer_group"],
)

OUTBOX_RELAY_LAG_SECONDS = Gauge(
    "outbox_relay_lag_seconds",
    "Age in seconds of the oldest unpublished event in the transactional outbox",
    ["channel"],
)

OUTBOX_UNPROCESSED_COUNT = Gauge(
    "outbox_unprocessed_count",
    "Total number of unpublished events in the outbox table",
    ["channel", "status"],
)

NATS_ACK_PENDING = Gauge(
    "nats_ack_pending",
    "Total pending unacknowledged messages on NATS JetStream consumer",
    ["stream", "consumer"],
)

REDIS_CACHE_HITS_TOTAL = Counter(
    "redis_cache_hits_total",
    "Total number of cache lookup hits",
    ["namespace"],
)

REDIS_CACHE_MISSES_TOTAL = Counter(
    "redis_cache_misses_total",
    "Total number of cache lookup misses",
    ["namespace"],
)

DB_POOL_CONNECTIONS_IN_USE = Gauge(
    "db_pool_connections_in_use",
    "Number of active connections currently checked out of the database pool",
    ["pool"],
)

DB_POOL_CONNECTIONS_IDLE = Gauge(
    "db_pool_connections_idle",
    "Number of idle connections sitting in the database pool",
    ["pool"],
)

ASSAY_INFERENCE_LATENCY_SECONDS = Histogram(
    "assay_inference_latency_seconds",
    "Latency of assay crop quality inference in seconds",
    ["model_id", "architecture"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

SYNC_PUSH_CONFLICTS_TOTAL = Counter(
    "sync_push_conflicts_total",
    "Total WatermelonDB sync push conflict occurrences",
    ["table"],
)

CONSENT_REVOCATIONS_TOTAL = Counter(
    "consent_revocations_total",
    "Total consent revocations processed",
    ["action"],
)

KAFKA_PUBLISH_FAILURES_TOTAL = Counter(
    "kafka_publish_failures_total",
    "Total number of failed Kafka event publish attempts",
    ["topic"],
)

CACHE_HIT_RATIO = Gauge(
    "cache_hit_ratio",
    "Current cache hit ratio (0.0 to 1.0)",
    ["namespace"],
)

DB_POOL_IN_USE = Gauge(
    "db_pool_in_use",
    "Database pool connections currently in use",
    ["pool"],
)

INFERENCE_LATENCY_SECONDS = Histogram(
    "inference_latency_seconds",
    "Model inference latency in seconds",
    ["model_id"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# ============================================================================
# Route Normalization (preventing label cardinality explosion)
# ============================================================================

UUID_REGEX = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
NUMERIC_ID_REGEX = re.compile(r"/\d+(?=/|$)")


def normalize_route_path(path: str) -> str:
    """Replace UUIDs and numeric IDs in route paths with templated placeholders."""
    p = UUID_REGEX.sub("{id}", path)
    p = NUMERIC_ID_REGEX.sub("/{id}", p)
    return p


# ============================================================================
# HTTP Metrics Middleware
# ============================================================================

class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """ASGI middleware for collecting request latencies, status codes, and error counts."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Exclude metrics and health endpoints from latency histograms to avoid feedback loops
        raw_path = request.url.path
        if raw_path in ("/metrics", "/health", "/health/live", "/health/ready", "/live", "/ready"):
            return await call_next(request)

        route_label = normalize_route_path(raw_path)
        method = request.method
        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            status_code = 500
            HTTP_REQUEST_ERRORS_TOTAL.labels(type=exc.__class__.__name__, route=route_label).inc()
            raise
        finally:
            duration = time.perf_counter() - start_time
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method, route=route_label, status_code=str(status_code)
            ).observe(duration)
            HTTP_REQUESTS_TOTAL.labels(
                method=method, route=route_label, status_code=str(status_code)
            ).inc()
            if status_code >= 400:
                HTTP_REQUEST_ERRORS_TOTAL.labels(
                    type=f"HTTP_{status_code}", route=route_label
                ).inc()


# ============================================================================
# Helper Tracking Functions
# ============================================================================

def track_redis_hit(namespace: str = "default") -> None:
    REDIS_CACHE_HITS_TOTAL.labels(namespace=namespace).inc()


def track_redis_miss(namespace: str = "default") -> None:
    REDIS_CACHE_MISSES_TOTAL.labels(namespace=namespace).inc()


def update_db_pool_metrics(in_use: int, idle: int, pool: str = "primary") -> None:
    DB_POOL_CONNECTIONS_IN_USE.labels(pool=pool).set(in_use)
    DB_POOL_CONNECTIONS_IDLE.labels(pool=pool).set(idle)


def track_outbox_metrics(unprocessed_count: int, oldest_lag_seconds: float = 0.0, channel: str = "kafka") -> None:
    OUTBOX_UNPROCESSED_COUNT.labels(channel=channel, status="pending").set(unprocessed_count)
    OUTBOX_RELAY_LAG_SECONDS.labels(channel=channel).set(oldest_lag_seconds)


def track_kafka_lag(topic: str, partition: int, consumer_group: str, lag: int) -> None:
    KAFKA_CONSUMER_LAG.labels(
        topic=topic, partition=str(partition), consumer_group=consumer_group
    ).set(lag)


def track_nats_ack_pending(stream: str, consumer: str, pending: int) -> None:
    NATS_ACK_PENDING.labels(stream=stream, consumer=consumer).set(pending)


def track_assay_inference(model_id: str, architecture: str, duration_seconds: float) -> None:
    ASSAY_INFERENCE_LATENCY_SECONDS.labels(
        model_id=model_id, architecture=architecture
    ).observe(duration_seconds)


def track_sync_conflict(table: str) -> None:
    SYNC_PUSH_CONFLICTS_TOTAL.labels(table=table).inc()


def track_consent_revocation(action: str = "revoked") -> None:
    CONSENT_REVOCATIONS_TOTAL.labels(action=action).inc()


def track_kafka_publish_failure(topic: str = "unknown") -> None:
    KAFKA_PUBLISH_FAILURES_TOTAL.labels(topic=topic).inc()


def track_inference_latency(model_id: str, duration_seconds: float) -> None:
    INFERENCE_LATENCY_SECONDS.labels(model_id=model_id).observe(duration_seconds)


# ============================================================================
# /metrics Authentication & Authorization
# ============================================================================

INTERNAL_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
]


def is_authorized_metrics_request(request: Request) -> bool:
    """Verify if the caller is authorized to view Prometheus metrics.

    Authorized if:
    1. Valid METRICS_BEARER_TOKEN or APP_METRICS_TOKEN provided in Authorization header, OR
    2. Request originates from internal/private IP space (when METRICS_ENFORCE_AUTH is not 'strict'), OR
    3. Running in development/local mode with no token configured.
    """
    configured_token = os.getenv("METRICS_BEARER_TOKEN", os.getenv("APP_METRICS_TOKEN", "")).strip()
    auth_header = request.headers.get("authorization", "")
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    elif "x-metrics-token" in request.headers:
        token = request.headers["x-metrics-token"].strip()

    # If explicit token configured, token match guarantees authorization
    if configured_token:
        return token == configured_token

    # Check internal client IP
    client_ip_str = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip_str and request.client:
        client_ip_str = request.client.host

    if client_ip_str:
        try:
            client_ip = ipaddress.ip_address(client_ip_str)
            for net in INTERNAL_IP_NETWORKS:
                if client_ip in net:
                    return True
        except ValueError:
            pass

    # Default to open in local development if no token configured
    env = os.getenv("APP_ENVIRONMENT", os.getenv("ENVIRONMENT", "local")).lower()
    return env in ("local", "dev", "development", "test")


async def metrics_endpoint(request: Request) -> Response:
    """Exposes Prometheus text exposition format to authorized scrapers."""
    if not is_authorized_metrics_request(request):
        return Response(
            content="Unauthorized metrics probe\n",
            status_code=403,
            media_type="text/plain",
        )

    # Automatically sample DB pool metrics if engine is attached to app.state
    try:
        db = getattr(request.app.state, "database", None)
        if db and hasattr(db, "_engine") and hasattr(db._engine, "pool"):
            pool = db._engine.pool
            checked_out = getattr(pool, "checkedout", lambda: 0)()
            checked_in = getattr(pool, "checkedin", lambda: 0)()
            update_db_pool_metrics(in_use=checked_out, idle=checked_in, pool="primary")
    except Exception:
        pass

    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
