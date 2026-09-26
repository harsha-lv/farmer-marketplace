"""OpenTelemetry instrumentation for FastAPI, SQLAlchemy, Redis, and aiokafka.

Configured by environment variables:
- OTEL_EXPORTER_OTLP_ENDPOINT: e.g. http://localhost:4317 or http://otel-collector:4317
- OTEL_SERVICE_NAME: e.g. agri-platform-backend (default)

When OTEL_EXPORTER_OTLP_ENDPOINT is unset or empty, instrumentation is a strict NO-OP.
"""

import logging
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("app.telemetry.otel")

_IS_INSTRUMENTED = False


def is_otel_enabled() -> bool:
    """Check if OpenTelemetry OTLP export is configured via environment."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    return bool(endpoint)


def setup_opentelemetry(app: Any | None = None, engine: Any | None = None) -> None:
    """Initialize OpenTelemetry tracer provider, OTLP span exporter, and auto-instrumentation.

    If OTEL_EXPORTER_OTLP_ENDPOINT is unset, this is a clean no-op.
    """
    global _IS_INSTRUMENTED
    if _IS_INSTRUMENTED:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT not set; OpenTelemetry tracing is in NO-OP mode.")
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "agri-platform-backend").strip()
    insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() in ("true", "1", "yes")

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # 1. Instrument FastAPI
        if app is not None:
            try:
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

                FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
                logger.info("OpenTelemetry instrumented FastAPI application.")
            except Exception as e:
                logger.warning("Failed to instrument FastAPI with OpenTelemetry: %s", e)

        # 2. Instrument SQLAlchemy
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

            if engine is not None:
                sync_eng = getattr(engine, "sync_engine", engine)
                SQLAlchemyInstrumentor().instrument(engine=sync_eng, tracer_provider=provider)
            else:
                SQLAlchemyInstrumentor().instrument(tracer_provider=provider)
            logger.info("OpenTelemetry instrumented SQLAlchemy.")
        except Exception as e:
            logger.warning("Failed to instrument SQLAlchemy with OpenTelemetry: %s", e)

        # 3. Instrument Redis
        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor

            RedisInstrumentor().instrument(tracer_provider=provider)
            logger.info("OpenTelemetry instrumented Redis.")
        except Exception as e:
            logger.warning("Failed to instrument Redis with OpenTelemetry: %s", e)

        _IS_INSTRUMENTED = True
        logger.info(
            "OpenTelemetry configured successfully (endpoint=%s, service=%s).",
            endpoint,
            service_name,
        )

    except Exception as exc:
        logger.error("Failed to initialize OpenTelemetry: %s", exc)


def instrument_kafka_producer(send_func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator or wrapper injecting trace context into Kafka message headers."""
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not is_otel_enabled():
            return await send_func(*args, **kwargs)

        try:
            from opentelemetry import trace
            from opentelemetry.trace.propagation.tracecontext import (
                TraceContextTextMapPropagator,
            )

            tracer = trace.get_tracer("aiokafka.producer")
            topic = kwargs.get("topic") or (args[0] if len(args) > 0 else "unknown")

            with tracer.start_as_current_span(f"kafka.send {topic}") as span:
                span.set_attribute("messaging.system", "kafka")
                span.set_attribute("messaging.destination", str(topic))
                headers = kwargs.get("headers") or []
                if isinstance(headers, list):
                    carrier: dict[str, str] = {}
                    TraceContextTextMapPropagator().inject(carrier)
                    for k, v in carrier.items():
                        headers.append((k, v.encode("utf-8")))
                    kwargs["headers"] = headers
                return await send_func(*args, **kwargs)
        except Exception:
            return await send_func(*args, **kwargs)

    return wrapper


def instrument_kafka_consumer_message(msg: Any) -> Any:
    """Extract OpenTelemetry traceparent from Kafka headers if present and start a span."""
    if not is_otel_enabled():
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        carrier: dict[str, str] = {}
        if hasattr(msg, "headers") and msg.headers:
            for k, v in msg.headers:
                carrier[k] = v.decode("utf-8") if isinstance(v, bytes) else str(v)

        ctx = TraceContextTextMapPropagator().extract(carrier)
        tracer = trace.get_tracer("aiokafka.consumer")
        topic = getattr(msg, "topic", "unknown")
        return tracer.start_span(f"kafka.process {topic}", context=ctx)
    except Exception:
        return None
