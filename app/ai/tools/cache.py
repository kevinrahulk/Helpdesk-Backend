"""
Lightweight TTL cache used to avoid re-calling the LLM for identical
inputs (e.g. re-opening the same ticket detail page repeatedly, or a
duplicate creation-assistant request).

This is an in-process cache, which is fine for a single-worker
deployment. For multi-worker / multi-instance deployments, swap
`InMemoryTTLCache` for a Redis-backed implementation that satisfies the
same `AICache` protocol — nothing else needs to change.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Protocol


class AICache(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...


class InMemoryTTLCache:
    """Process-local cache with per-entry TTL. Not shared across workers."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._store[key] = (time.monotonic() + ttl_seconds, value)

    def clear(self) -> None:
        self._store.clear()


def make_cache_key(*parts: str) -> str:
    """Stable cache key from arbitrary string parts (e.g. node name + payload hash)."""
    joined = "||".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# Process-wide singleton. Swap this import for a Redis-backed cache in
# production multi-worker deployments (see docstring above).
ai_cache: AICache = InMemoryTTLCache()
