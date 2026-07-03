"""
Process-local token-bucket rate limiter for outbound LLM calls.

Protects against runaway cost/usage from a single FastAPI worker. For a
multi-worker deployment, back this with Redis (e.g. `redis-py`'s
`INCR`/`EXPIRE` pattern) behind the same `acquire()` interface.
"""

from __future__ import annotations

import threading
import time

# pyrefly: ignore [missing-import]
from fastapi import HTTPException, status


class TokenBucketRateLimiter:
    def __init__(self, max_per_minute: int) -> None:
        self._capacity = max_per_minute
        self._tokens = float(max_per_minute)
        self._refill_rate = max_per_minute / 60.0  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def acquire(self, cost: float = 1.0) -> None:
        with self._lock:
            self._refill()
            if self._tokens < cost:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="AI assistant is receiving too many requests right now. Please retry shortly.",
                )
            self._tokens -= cost


_limiter_singleton: TokenBucketRateLimiter | None = None


def get_rate_limiter() -> TokenBucketRateLimiter:
    global _limiter_singleton
    if _limiter_singleton is None:
        from app.ai.config import get_ai_settings

        _limiter_singleton = TokenBucketRateLimiter(get_ai_settings().AI_RATE_LIMIT_PER_MINUTE)
    return _limiter_singleton
