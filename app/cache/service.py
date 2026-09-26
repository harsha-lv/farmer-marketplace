"""Cache-aside service layer with single-flight stampede prevention and tag invalidation.

Guarantees:
  - Cache-aside helpers: get_or_set, mget_or_set
  - Pattern and tag-based cache invalidation
  - Single-flight distributed lock (SET NX PX) to eliminate thundering herd on hot mandi keys
  - Transparent JSON serialization with ISO-8601 datetime and UUID support
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

from app.cache.client import CacheClient, get_cache_client, get_ttl_for_policy

logger = logging.getLogger("app.cache.service")

T = TypeVar("T")


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def serialize_value(value: Any) -> str:
    """Serialize Python object to JSON string with rich type support."""
    if isinstance(value, str):
        return value
    return json.dumps(value, default=_json_default)


def deserialize_value(raw: str | None) -> Any:
    """Deserialize JSON string into native Python object."""
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


class CacheService:
    """Production-grade Cache-Aside Service."""

    def __init__(self, client: CacheClient | None = None) -> None:
        self.client = client or get_cache_client()
        # In-memory tag registry for tag-based invalidation
        self._tag_registry: dict[str, set[str]] = {}
        self._tag_lock = asyncio.Lock()

    async def _register_tags(self, key: str, tags: list[str]) -> None:
        """Associate cache key with tags."""
        async with self._tag_lock:
            for tag in tags:
                self._tag_registry.setdefault(tag, set()).add(key)

    async def get_or_set(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[T]],
        ttl: int | None = None,
        policy: str | None = None,
        tags: list[str] | None = None,
    ) -> T:
        """Cache-aside read-through helper.

        If cached, returns deserialized value immediately.
        If missing, executes fetch_fn, caches value with TTL, registers tags, and returns.
        """
        cached_raw = await self.client.get(key)
        if cached_raw is not None:
            if cached_raw == "__NULL__":
                return None
            return deserialize_value(cached_raw)

        # Cache miss -> invoke fetcher
        value = await fetch_fn()
        if value is None:
            # Negative lookup caching (30s)
            neg_ttl = get_ttl_for_policy("negative_lookup")
            await self.client.set(key, "__NULL__", ex=neg_ttl)
            return None

        effective_ttl = ttl or (get_ttl_for_policy(policy) if policy else get_ttl_for_policy("default"))
        serialized = serialize_value(value)
        await self.client.set(key, serialized, ex=effective_ttl)

        if tags:
            await self._register_tags(key, tags)

        return value

    async def mget_or_set(
        self,
        keys: list[str],
        fetch_fn: Callable[[list[str]], Awaitable[dict[str, T]]],
        ttl: int | None = None,
        policy: str | None = None,
    ) -> dict[str, T]:
        """Batch cache-aside helper for multiple keys."""
        if not keys:
            return {}

        results: dict[str, Any] = {}
        cached_values = await self.client.mget(*keys)

        missing_keys: list[str] = []
        for k, v in zip(keys, cached_values, strict=False):
            if v is not None:
                results[k] = None if v == "__NULL__" else deserialize_value(v)
            else:
                missing_keys.append(k)

        if missing_keys:
            fetched_dict = await fetch_fn(missing_keys)
            effective_ttl = ttl or (get_ttl_for_policy(policy) if policy else get_ttl_for_policy("default"))

            for k, val in fetched_dict.items():
                results[k] = val
                stored_val = "__NULL__" if val is None else serialize_value(val)
                await self.client.set(k, stored_val, ex=effective_ttl)

        return results

    async def get_or_set_locked(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[T]],
        ttl: int | None = None,
        policy: str | None = None,
        lock_ttl_ms: int = 5000,
        wait_timeout_s: float = 3.0,
    ) -> T:
        """Cache-aside with single-flight mutex lock (SET NX PX) to prevent cache stampede.

        Hot mandi keys / rollups will have exactly ONE worker compute the result while
        concurrent requests await the populated cache.
        """
        # Fast-path check
        cached_raw = await self.client.get(key)
        if cached_raw is not None:
            if cached_raw == "__NULL__":
                return None
            return deserialize_value(cached_raw)

        lock_key = f"{key}:lock"
        lock_token = uuid.uuid4().hex
        acquired = await self.client.set(lock_key, lock_token, px=lock_ttl_ms, nx=True)

        if acquired:
            try:
                # Double-check cache in case previous holder just completed
                double_check = await self.client.get(key)
                if double_check is not None:
                    if double_check == "__NULL__":
                        return None
                    return deserialize_value(double_check)

                # Holder computes and populates cache
                value = await fetch_fn()
                effective_ttl = ttl or (get_ttl_for_policy(policy) if policy else get_ttl_for_policy("default"))
                stored_val = "__NULL__" if value is None else serialize_value(value)
                await self.client.set(key, stored_val, ex=effective_ttl)
                return value
            finally:
                # Release lock if still owner
                cur_lock = await self.client.get(lock_key)
                if cur_lock == lock_token:
                    await self.client.delete(lock_key)
        else:
            # Concurrent requester: wait for lock holder to populate cache
            start_time = time.monotonic()
            poll_interval = 0.05  # 50ms polling

            while (time.monotonic() - start_time) < wait_timeout_s:
                await asyncio.sleep(poll_interval)
                cached = await self.client.get(key)
                if cached is not None:
                    if cached == "__NULL__":
                        return None
                    return deserialize_value(cached)

            # Fallback if timeout reached: compute directly to avoid hanging
            logger.warning("Single-flight lock wait timeout for key %s; evaluating directly.", key)
            return await fetch_fn()

    async def invalidate(self, pattern: str) -> int:
        """Invalidate all cache keys matching a wildcard pattern (e.g. agri:*:price:*)."""
        deleted_count = await self.client.flush_pattern(pattern)
        logger.info("Invalidated pattern '%s' (%d keys removed)", pattern, deleted_count)
        return deleted_count

    async def invalidate_tags(self, *tags: str) -> int:
        """Invalidate all cache keys registered under the given tags."""
        keys_to_delete: set[str] = set()
        async with self._tag_lock:
            for t in tags:
                registered = self._tag_registry.pop(t, None)
                if registered:
                    keys_to_delete.update(registered)

        if keys_to_delete:
            count = await self.client.delete(*keys_to_delete)
            logger.info("Invalidated tags %s (%d keys removed)", tags, count)
            return count
        return 0


# Singleton CacheService instance
_cache_service_instance: CacheService | None = None


def get_cache_service(client: CacheClient | None = None) -> CacheService:
    global _cache_service_instance
    if _cache_service_instance is None:
        _cache_service_instance = CacheService(client=client)
    return _cache_service_instance


def reset_cache_service() -> None:
    global _cache_service_instance
    _cache_service_instance = None
