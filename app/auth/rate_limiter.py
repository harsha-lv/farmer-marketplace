"""Token-bucket rate limiter with IP and account scoping, per-tier limits, and 429 Retry-After handling."""

import asyncio
import math
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.config import get_settings


@dataclass
class TokenBucket:
    capacity: float
    refill_rate: float  # tokens per second
    tokens: float
    last_update: float

    def consume(self, tokens: float = 1.0) -> tuple[bool, int]:
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens up to capacity
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0

        # Calculate seconds until at least 1 token is available
        needed = tokens - self.tokens
        retry_after = math.ceil(needed / self.refill_rate) if self.refill_rate > 0 else 60
        return False, max(1, retry_after)


class InMemoryTokenBucketLimiter:
    """Thread-safe in-memory token bucket rate limiter with automatic TTL purge."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()

    async def check_rate_limit(
        self,
        key: str,
        limit_per_minute: int,
        cost: float = 1.0,
    ) -> tuple[bool, int]:
        async with self._lock:
            now = time.monotonic()
            # Periodic cleanup of idle buckets (every 5 minutes)
            if now - self._last_cleanup > 300:
                self._cleanup(now)
                self._last_cleanup = now

            refill_rate = limit_per_minute / 60.0
            capacity = float(limit_per_minute)

            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(
                    capacity=capacity,
                    refill_rate=refill_rate,
                    tokens=capacity,
                    last_update=now,
                )
                self._buckets[key] = bucket

            return bucket.consume(cost)

    def _cleanup(self, now: float) -> None:
        stale_keys = [
            k for k, b in self._buckets.items()
            if (now - b.last_update) > 1800  # 30 minutes of inactivity
        ]
        for k in stale_keys:
            del self._buckets[k]

    def reset(self) -> None:
        self._buckets.clear()


# Global limiter instance
limiter = InMemoryTokenBucketLimiter()


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


async def check_login_rate_limit(request: Request, account_identifier: str | None = None) -> None:
    """Enforce dual rate limiting on auth endpoints: by IP and by account identifier."""
    settings = get_settings()
    ip = get_client_ip(request)

    # 1. Check IP rate limit (20 req / min)
    ip_key = f"rl:auth:ip:{ip}"
    allowed_ip, retry_after_ip = await limiter.check_rate_limit(
        ip_key,
        limit_per_minute=settings.rate_limit_per_minute_auth,
    )
    if not allowed_ip:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for authentication requests. Please try again later.",
            headers={"Retry-After": str(retry_after_ip)},
        )

    # 2. Check account rate limit (5 failed/total attempts per min)
    if account_identifier:
        clean_acc = account_identifier.strip().lower()
        acc_key = f"rl:auth:account:{clean_acc}"
        allowed_acc, retry_after_acc = await limiter.check_rate_limit(
            acc_key,
            limit_per_minute=10,  # 10 attempts per minute per account
        )
        if not allowed_acc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts for account {clean_acc}. Please wait before retrying.",
                headers={"Retry-After": str(retry_after_acc)},
            )


async def check_refresh_rate_limit(request: Request) -> None:
    """Enforce rate limiting on refresh endpoints."""
    settings = get_settings()
    ip = get_client_ip(request)
    key = f"rl:refresh:ip:{ip}"
    allowed, retry_after = await limiter.check_rate_limit(
        key,
        limit_per_minute=settings.rate_limit_per_minute_auth,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for token refresh. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
