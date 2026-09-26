"""Token-bucket rate limiting primitives backed by Redis and in-memory fallback.

Guarantees:
  - Token-bucket algorithm with continuous replenishment
  - Per-IP, per-API-key, and per-endpoint tiers
  - Exposes standardized 429 response headers:
      - Retry-After
      - X-RateLimit-Limit
      - X-RateLimit-Remaining
      - X-RateLimit-Reset
"""

import json
import logging
import time
from dataclasses import dataclass

from fastapi import Request

from app.cache.client import CacheClient, format_cache_key, get_cache_client
from app.config import get_settings

logger = logging.getLogger("app.cache.rate_limit")


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset: int
    retry_after: int
    category: str
    key: str

    def get_headers(self) -> dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(self.reset),
        }
        if not self.allowed:
            headers["Retry-After"] = str(max(1, self.retry_after))
        return headers


# Endpoint classification categories
AUTH_KEYWORDS = frozenset(["auth", "login", "token", "password", "consents", "agristack"])
PRICE_KEYWORDS = frozenset(["prices", "mandi", "rollups", "volatility", "forecast"])


def classify_request_category(path: str) -> str:
    path_lower = path.lower()
    for kw in AUTH_KEYWORDS:
        if kw in path_lower:
            return "auth"
    for kw in PRICE_KEYWORDS:
        if kw in path_lower:
            return "prices"
    return "general"


class TokenBucketRateLimiter:
    """Async token-bucket rate limiter.

    Replenishes tokens smoothly over time and supports burst capacities.
    """

    def __init__(self, client: CacheClient | None = None) -> None:
        self.client = client or get_cache_client()
        self.settings = get_settings()

    def get_tier_config(self, category: str) -> tuple[int, float]:
        """Returns (capacity, refill_rate_per_sec) for a given tier category."""
        if category == "auth":
            limit = self.settings.rate_limit_per_minute_auth  # 20
        elif category == "prices":
            limit = self.settings.rate_limit_per_minute_prices  # 500
        else:
            limit = self.settings.rate_limit_per_minute_default  # 100

        refill_rate = limit / 60.0
        return limit, refill_rate

    def resolve_subject(self, request: Request) -> tuple[str, str]:
        """Extract rate limiting subject: per-API-key if present, else per-IP."""
        # 1. Check API key header or Bearer token prefix
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer ak_live_"):
                api_key = auth_header.replace("Bearer ", "").strip()

        if api_key:
            # Use short prefix of API key as subject identifier
            subject_id = f"apikey:{api_key[:16]}"
            subject_type = "api_key"
        else:
            # Per-IP identification
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()
            elif request.client and request.client.host:
                client_ip = request.client.host
            else:
                client_ip = "127.0.0.1"
            subject_id = f"ip:{client_ip}"
            subject_type = "ip"

        return subject_id, subject_type

    async def check(
        self,
        key: str,
        category: str = "general",
        cost: float = 1.0,
    ) -> RateLimitResult:
        """Check rate limit bucket for key using token bucket algorithm."""
        capacity, refill_rate = self.get_tier_config(category)
        now = time.time()
        cache_key = format_cache_key("rate_limit", f"{category}:{key}")

        raw_state = await self.client.get(cache_key)
        if raw_state:
            try:
                state = json.loads(raw_state)
                last_tokens = float(state.get("tokens", capacity))
                last_updated = float(state.get("last_updated", now))
            except Exception:
                last_tokens = float(capacity)
                last_updated = now
        else:
            last_tokens = float(capacity)
            last_updated = now

        # Replenish tokens based on elapsed time
        elapsed = max(0.0, now - last_updated)
        replenished = min(float(capacity), last_tokens + (elapsed * refill_rate))

        if replenished >= cost:
            remaining_tokens = replenished - cost
            allowed = True
            retry_after = 0
            # Reset time is when bucket refills to capacity
            missing_tokens = capacity - remaining_tokens
            reset_time = int(now + (missing_tokens / refill_rate)) if refill_rate > 0 else int(now + 60)
        else:
            remaining_tokens = replenished
            allowed = False
            needed = cost - remaining_tokens
            retry_after = int(needed / refill_rate) + 1 if refill_rate > 0 else 60
            reset_time = int(now + retry_after)

        # Store updated state with TTL covering refill duration
        ttl = max(60, int((capacity / refill_rate) * 2)) if refill_rate > 0 else 120
        new_state = {
            "tokens": remaining_tokens,
            "last_updated": now,
        }
        await self.client.set(cache_key, json.dumps(new_state), ex=ttl)

        return RateLimitResult(
            allowed=allowed,
            limit=capacity,
            remaining=int(remaining_tokens),
            reset=reset_time,
            retry_after=retry_after,
            category=category,
            key=key,
        )

    async def check_request(self, request: Request, cost: float = 1.0) -> RateLimitResult:
        """Convenience method checking rate limit for an incoming FastAPI request."""
        path = request.url.path
        category = classify_request_category(path)
        subject_id, _ = self.resolve_subject(request)
        return await self.check(key=subject_id, category=category, cost=cost)


# Singleton TokenBucketRateLimiter
_limiter_instance: TokenBucketRateLimiter | None = None


def get_token_bucket_limiter(client: CacheClient | None = None) -> TokenBucketRateLimiter:
    global _limiter_instance
    if _limiter_instance is None:
        _limiter_instance = TokenBucketRateLimiter(client=client)
    return _limiter_instance
