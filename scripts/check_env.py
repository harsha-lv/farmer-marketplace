#!/usr/bin/env python3
"""Environment and connectivity validation for the Agri-Market Intelligence Platform.

Usage:
    python scripts/check_env.py [--production] [--timeout 5]

Exit codes:
    0  All checks passed.
    1  One or more checks failed (details printed to stderr).

Checks performed:
  1. Pydantic-settings loads without error (catches typos / type mismatches).
  2. production() guard if --production flag given.
  3. DATABASE_URL reachable (asyncpg ping).
  4. REDIS_URL reachable (ping).
  5. KAFKA_BOOTSTRAP_SERVERS reachable (admin list_topics).
  6. NATS_URL reachable (JS account info).
  7. OTEL endpoint reported if configured.
  8. Required secrets present (non-empty) for production tier.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import NamedTuple

OK = "\033[92m[OK]   \033[0m"
WARN = "\033[93m[WARN] \033[0m"
FAIL = "\033[91m[FAIL] \033[0m"
SKIP = "\033[90m[SKIP] \033[0m"


class Result(NamedTuple):
    label: str
    ok: bool
    message: str
    is_warning: bool = False


results: list[Result] = []


def record(label: str, ok: bool, message: str, *, warn: bool = False) -> None:
    results.append(Result(label=label, ok=ok, message=message, is_warning=warn))
    icon = OK if ok else (WARN if warn else FAIL)
    print(f"{icon} {label}: {message}")


def record_skip(label: str, reason: str) -> None:
    results.append(Result(label=label, ok=True, message=reason, is_warning=False))
    print(f"{SKIP} {label}: {reason}")


# ── 1. Settings load ──────────────────────────────────────────────────────────

def check_settings_load() -> "Settings | None":  # type: ignore[name-defined]
    try:
        # Invalidate lru_cache so we always get a fresh load
        from app.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        record("settings_load", True, "pydantic-settings parsed without error.")
        return s
    except Exception as exc:
        record("settings_load", False, f"Settings failed to load: {exc}")
        return None


# ── 2. Production guard ───────────────────────────────────────────────────────

def check_production_guard(settings: "Settings") -> None:  # type: ignore[name-defined]
    try:
        settings.validate_production()
        record("production_guard", True, "All required production settings are present.")
    except ValueError as exc:
        record("production_guard", False, str(exc))


# ── 3. Database ───────────────────────────────────────────────────────────────

async def check_database(settings: "Settings", timeout: float) -> None:  # type: ignore[name-defined]
    url = settings.database_url
    if not url:
        record_skip("database", "APP_DATABASE_URL is not configured.")
        return
    try:
        import asyncpg  # type: ignore[import]
        conn = await asyncio.wait_for(
            asyncpg.connect(url.replace("+asyncpg", "")),
            timeout=timeout,
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        record("database", True, f"Connected to PostgreSQL at {_mask_url(url)}.")
    except asyncio.TimeoutError:
        record("database", False, f"Connection timed out after {timeout}s.")
    except Exception as exc:
        record("database", False, f"Connection failed: {exc}")


# ── 4. Redis ──────────────────────────────────────────────────────────────────

async def check_redis(settings: "Settings", timeout: float) -> None:  # type: ignore[name-defined]
    url = settings.redis_url
    if not url:
        record_skip("redis", "APP_REDIS_URL is not configured (cache disabled).")
        return
    try:
        import redis.asyncio as aioredis  # type: ignore[import]
        client = aioredis.from_url(url, socket_connect_timeout=timeout, socket_timeout=timeout)
        await asyncio.wait_for(client.ping(), timeout=timeout)
        await client.aclose()
        record("redis", True, f"PING OK at {_mask_url(url)}.")
    except asyncio.TimeoutError:
        record("redis", False, f"PING timed out after {timeout}s.")
    except Exception as exc:
        record("redis", False, f"Connection failed: {exc}")


# ── 5. Kafka ──────────────────────────────────────────────────────────────────

async def check_kafka(settings: "Settings", timeout: float) -> None:  # type: ignore[name-defined]
    servers = settings.kafka_bootstrap_servers
    if not servers:
        record_skip("kafka", "APP_KAFKA_BOOTSTRAP_SERVERS is not configured.")
        return
    try:
        from aiokafka.admin import AIOKafkaAdminClient  # type: ignore[import]
        admin = AIOKafkaAdminClient(
            bootstrap_servers=servers,
            client_id="env-checker",
            request_timeout_ms=int(timeout * 1000),
        )
        await asyncio.wait_for(admin.start(), timeout=timeout + 2)
        topics = await asyncio.wait_for(admin.list_topics(), timeout=timeout)
        await admin.close()
        record("kafka", True, f"Connected. {len(topics)} topic(s) visible at {servers}.")
    except asyncio.TimeoutError:
        record("kafka", False, f"Connection timed out after {timeout}s.")
    except Exception as exc:
        record("kafka", False, f"Connection failed: {exc}")


# ── 6. NATS ───────────────────────────────────────────────────────────────────

async def check_nats(settings: "Settings", timeout: float) -> None:  # type: ignore[name-defined]
    url = settings.nats_url
    if not url:
        record_skip("nats", "APP_NATS_URL is not configured.")
        return
    try:
        import nats  # type: ignore[import]
        nc = await asyncio.wait_for(nats.connect(url), timeout=timeout)
        js = nc.jetstream()
        info = await asyncio.wait_for(js.account_info(), timeout=timeout)
        await nc.drain()
        record(
            "nats",
            True,
            f"JetStream OK at {url}. "
            f"Streams={info.streams}, Consumers={info.consumers}.",
        )
    except asyncio.TimeoutError:
        record("nats", False, f"Connection timed out after {timeout}s.")
    except Exception as exc:
        record("nats", False, f"Connection failed: {exc}")


# ── 7. OTEL endpoint report ───────────────────────────────────────────────────

def check_otel(settings: "Settings") -> None:  # type: ignore[name-defined]
    ep = settings.otel_exporter_otlp_endpoint
    if ep:
        record("otel", True, f"OTLP endpoint configured: {ep} (service={settings.otel_service_name}).")
    else:
        record_skip("otel", "OTEL_EXPORTER_OTLP_ENDPOINT not set — tracing is NO-OP.")


# ── 8. Required secrets (non-production too) ──────────────────────────────────

def check_secrets_present(settings: "Settings") -> None:  # type: ignore[name-defined]
    weak_jwt = "dev-secret-key-change-in-production-at-least-32-chars-long"
    weak_assay = "assay-tamper-evident-hmac-secret-key-32chars"

    if settings.jwt_secret_key == weak_jwt:
        record(
            "jwt_secret",
            False,
            "APP_JWT_SECRET_KEY is still the dev placeholder.",
            warn=settings.environment != "production",
        )
    else:
        record("jwt_secret", True, "APP_JWT_SECRET_KEY is set.")

    if settings.assay_hmac_secret == weak_assay:
        record(
            "assay_hmac_secret",
            False,
            "APP_ASSAY_HMAC_SECRET is still the dev placeholder.",
            warn=settings.environment != "production",
        )
    else:
        record("assay_hmac_secret", True, "APP_ASSAY_HMAC_SECRET is set.")

    if not settings.metrics_token:
        record(
            "metrics_token",
            False,
            "METRICS_BEARER_TOKEN is empty — /metrics is unprotected.",
            warn=settings.environment != "production",
        )
    else:
        record("metrics_token", True, "METRICS_BEARER_TOKEN is set.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mask_url(url: str) -> str:
    """Redact password from a DSN for display."""
    import re
    return re.sub(r"(:)[^:@]+(@)", r"\1***\2", url)


# ── Entry point ───────────────────────────────────────────────────────────────

async def run_all(args: argparse.Namespace) -> int:
    settings = check_settings_load()
    if settings is None:
        return 1

    if args.production:
        check_production_guard(settings)

    check_otel(settings)
    check_secrets_present(settings)

    await check_database(settings, args.timeout)
    await check_redis(settings, args.timeout)
    await check_kafka(settings, args.timeout)
    await check_nats(settings, args.timeout)

    print()
    failed = [r for r in results if not r.ok and not r.is_warning]
    warnings = [r for r in results if r.is_warning]
    passed = [r for r in results if r.ok]

    print(f"Results: {len(passed)} passed, {len(warnings)} warning(s), {len(failed)} failed.")
    return 0 if not failed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Check environment and connectivity.")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Run the production guard (fails on missing required secrets).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-check connection timeout in seconds (default: 5).",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run_all(args)))


if __name__ == "__main__":
    main()
