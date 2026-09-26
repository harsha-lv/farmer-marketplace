"""Production-grade async cache client with Redis connection pooling and LRU fallback.

Guarantees:
  - Singleton async client with connection pool and health check
  - Automatic fallback to an in-process LRU (cachetools) with a logged warning when
    Redis is unreachable — requests must NEVER fail because of the cache
  - Key namespacing: agri:{tenant}:{domain}:{id} with tenant from context
  - Standardized TTL policy table
"""

import asyncio
import logging
import time
from fnmatch import fnmatch
from typing import Any

from cachetools import LRUCache

from app.config import Settings, get_settings

logger = logging.getLogger("app.cache.client")

# Standardized TTL policies (in seconds)
TTL_POLICIES: dict[str, int] = {
    "price_snapshot": 60,       # 60s
    "vwap": 300,                 # 300s (5 min)
    "farmer_profile": 900,       # 900s (15 min)
    "lot_availability": 30,      # 30s
    "consent_status": 300,       # 300s (5 min)
    "negative_lookup": 30,       # 30s
    "idempotency": 86400,        # 24 hours
    "default": 300,              # 5 min fallback
}


def get_ttl_for_policy(policy_name: str) -> int:
    """Retrieve TTL in seconds for a named policy with safe fallback."""
    return TTL_POLICIES.get(policy_name.lower(), TTL_POLICIES["default"])


def format_cache_key(domain: str, id_: str, tenant: str | None = None) -> str:
    """Format canonical namespaced cache key: agri:{tenant}:{domain}:{id}."""
    clean_tenant = str(tenant).strip() if tenant else "public"
    return f"agri:{clean_tenant}:{domain}:{id_}"


class InMemoryCacheEntry:
    __slots__ = ("expires_at", "value")

    def __init__(self, value: str, expires_at: float | None = None) -> None:
        self.value = value
        self.expires_at = expires_at

    def is_expired(self, now: float) -> bool:
        return self.expires_at is not None and now > self.expires_at


class InMemoryLRUCache:
    """In-process thread-safe LRU cache with TTL expiration tracking."""

    def __init__(self, maxsize: int = 10000) -> None:
        self.maxsize = maxsize
        self._cache: LRUCache[str, InMemoryCacheEntry] = LRUCache(maxsize=maxsize)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        now = time.monotonic()
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired(now):
                self._cache.pop(key, None)
                return None
            return entry.value

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
    ) -> bool:
        now = time.monotonic()
        ttl_seconds = ex if ex is not None else ((px / 1000.0) if px is not None else None)
        expires_at = (now + ttl_seconds) if ttl_seconds is not None else None

        async with self._lock:
            existing = self._cache.get(key)
            if existing is not None and not existing.is_expired(now) and nx:
                return False
            self._cache[key] = InMemoryCacheEntry(value, expires_at)
            return True

    async def delete(self, *keys: str) -> int:
        count = 0
        async with self._lock:
            for k in keys:
                if self._cache.pop(k, None) is not None:
                    count += 1
        return count

    async def exists(self, key: str) -> bool:
        val = await self.get(key)
        return val is not None

    async def keys(self, pattern: str) -> list[str]:
        now = time.monotonic()
        matched = []
        async with self._lock:
            keys_to_purge = []
            for k, entry in list(self._cache.items()):
                if entry.is_expired(now):
                    keys_to_purge.append(k)
                    continue
                if fnmatch(k, pattern):
                    matched.append(k)
            for k in keys_to_purge:
                self._cache.pop(k, None)
        return matched

    async def mget(self, *keys: str) -> list[str | None]:
        results = []
        for k in keys:
            results.append(await self.get(k))
        return results

    async def flush_pattern(self, pattern: str) -> int:
        matched = await self.keys(pattern)
        if matched:
            return await self.delete(*matched)
        return 0

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()


class CacheClient:
    """Async Redis client wrapper with connection pooling, health checks,

    and seamless in-process LRU fallback.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.enabled = self.settings.cache_enabled
        self.redis_url = self.settings.redis_url.strip()
        self.pool_size = self.settings.redis_pool_size
        self.timeout_seconds = self.settings.redis_timeout_ms / 1000.0

        self._redis: Any = None
        self._pool: Any = None
        self._memory_cache = InMemoryLRUCache(maxsize=10000)
        self._is_redis_available = False
        self._last_warning_time: float = 0.0

    def _warn_degraded(self, exc: Exception | str) -> None:
        """Log degraded mode warning with rate limiting to avoid log floods."""
        now = time.time()
        if now - self._last_warning_time > 60.0:
            logger.warning(
                "Redis cache unavailable (%s). Gracefully degrading to in-process LRU cache.",
                exc,
            )
            self._last_warning_time = now

    async def initialize(self) -> None:
        """Initialize connection pool to Redis if URL is provided."""
        if not self.enabled:
            logger.info("Cache layer is disabled via settings (CACHE_ENABLED=False).")
            return

        if not self.redis_url:
            self._is_redis_available = False
            return

        try:
            import redis.asyncio as aioredis

            self._pool = aioredis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.pool_size,
                socket_timeout=self.timeout_seconds,
                socket_connect_timeout=self.timeout_seconds,
                decode_responses=True,
            )
            self._redis = aioredis.Redis(connection_pool=self._pool)
            # Perform initial ping probe
            await asyncio.wait_for(self._redis.ping(), timeout=self.timeout_seconds)
            self._is_redis_available = True
            logger.info("Connected to Redis cache at %s (pool_size=%d)", self.redis_url, self.pool_size)
        except Exception as exc:
            self._is_redis_available = False
            self._warn_degraded(exc)

    async def ping(self) -> bool:
        """Health check probe. Returns True if Redis is healthy or LRU fallback is operating."""
        if not self.enabled:
            return False
        if self._redis:
            try:
                pong = await asyncio.wait_for(self._redis.ping(), timeout=self.timeout_seconds)
                self._is_redis_available = bool(pong)
                return self._is_redis_available
            except Exception as exc:
                self._is_redis_available = False
                self._warn_degraded(exc)
        return True  # In-memory LRU is operational

    async def get(self, key: str) -> str | None:
        """Retrieve value by key. Never raises on backend outage."""
        if not self.enabled:
            return None

        from app.telemetry.metrics import track_redis_hit, track_redis_miss

        if self._is_redis_available and self._redis:
            try:
                val = await asyncio.wait_for(self._redis.get(key), timeout=self.timeout_seconds)
                if val is not None:
                    track_redis_hit(namespace="redis")
                else:
                    track_redis_miss(namespace="redis")
                return val
            except Exception as exc:
                self._is_redis_available = False
                self._warn_degraded(exc)

        val = await self._memory_cache.get(key)
        if val is not None:
            track_redis_hit(namespace="memory")
        else:
            track_redis_miss(namespace="memory")
        return val

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
    ) -> bool:
        """Store key-value with TTL and NX conditions. Never raises on backend outage."""
        if not self.enabled:
            return False

        if self._is_redis_available and self._redis:
            try:
                res = await asyncio.wait_for(
                    self._redis.set(key, value, ex=ex, px=px, nx=nx),
                    timeout=self.timeout_seconds,
                )
                return bool(res)
            except Exception as exc:
                self._is_redis_available = False
                self._warn_degraded(exc)

        return await self._memory_cache.set(key, value, ex=ex, px=px, nx=nx)

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        """Store key-value with explicit TTL in seconds."""
        return await self.set(key, value, ex=seconds)

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        if not self.enabled or not keys:
            return 0

        redis_deleted = 0
        if self._is_redis_available and self._redis:
            try:
                redis_deleted = await asyncio.wait_for(
                    self._redis.delete(*keys),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                self._is_redis_available = False
                self._warn_degraded(exc)

        mem_deleted = await self._memory_cache.delete(*keys)
        return max(redis_deleted, mem_deleted)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.enabled:
            return False

        if self._is_redis_available and self._redis:
            try:
                res = await asyncio.wait_for(self._redis.exists(key), timeout=self.timeout_seconds)
                return bool(res)
            except Exception as exc:
                self._is_redis_available = False
                self._warn_degraded(exc)

        return await self._memory_cache.exists(key)

    async def keys(self, pattern: str) -> list[str]:
        """Find keys matching a pattern."""
        if not self.enabled:
            return []

        if self._is_redis_available and self._redis:
            try:
                return await asyncio.wait_for(self._redis.keys(pattern), timeout=self.timeout_seconds)
            except Exception as exc:
                self._is_redis_available = False
                self._warn_degraded(exc)

        return await self._memory_cache.keys(pattern)

    async def mget(self, *keys: str) -> list[str | None]:
        """Multi-get values by keys."""
        if not self.enabled or not keys:
            return [None] * len(keys)

        if self._is_redis_available and self._redis:
            try:
                return await asyncio.wait_for(self._redis.mget(*keys), timeout=self.timeout_seconds)
            except Exception as exc:
                self._is_redis_available = False
                self._warn_degraded(exc)

        return await self._memory_cache.mget(*keys)

    async def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern."""
        if not self.enabled:
            return 0

        redis_count = 0
        if self._is_redis_available and self._redis:
            try:
                matched_keys = await asyncio.wait_for(self._redis.keys(pattern), timeout=self.timeout_seconds)
                if matched_keys:
                    redis_count = await asyncio.wait_for(self._redis.delete(*matched_keys), timeout=self.timeout_seconds)
            except Exception as exc:
                self._is_redis_available = False
                self._warn_degraded(exc)

        mem_count = await self._memory_cache.flush_pattern(pattern)
        return max(redis_count, mem_count)

    async def close(self) -> None:
        """Gracefully close Redis pool and connection."""
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass
        if self._pool:
            try:
                await self._pool.disconnect()
            except Exception:
                pass
        await self._memory_cache.clear()
        self._is_redis_available = False


# Singleton CacheClient instance
_cache_client_instance: CacheClient | None = None


def get_cache_client(settings: Settings | None = None) -> CacheClient:
    """Retrieve global singleton CacheClient instance."""
    global _cache_client_instance
    if _cache_client_instance is None:
        _cache_client_instance = CacheClient(settings=settings)
    return _cache_client_instance


def reset_cache_client() -> None:
    """Reset singleton instance (primarily for tests)."""
    global _cache_client_instance
    _cache_client_instance = None
