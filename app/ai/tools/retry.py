"""Generic retry-with-backoff helpers used by the LLM layer and tool nodes."""

from __future__ import annotations
import asyncio
import functools
import logging
import random
import time
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger("app.ai.retry")

def _delay(attempt: int, base_delay: float) -> float:
    # exponential backoff with jitter
    return base_delay * (2 ** attempt) + random.uniform(0, base_delay)


_NON_RETRIABLE_NAMES = {
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "BadRequestError",
    "InvalidRequestError",
    "UnprocessableEntityError",
    "PermissionError",
}

_NON_RETRIABLE_STATUS_CODES = {400, 401, 402, 403, 404, 422}


def _is_retriable(exc: BaseException) -> bool:
    """Best-effort check for whether retrying `exc` could plausibly help.

    Defaults to True (retry) for anything it can't confidently classify,
    since a false positive here just costs one extra attempt, while a
    false negative would silently stop retrying a genuinely transient
    error (e.g. a timeout or rate limit).
    """
    if type(exc).__name__ in _NON_RETRIABLE_NAMES:
        return False

    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and status_code in _NON_RETRIABLE_STATUS_CODES:
        return False

    return True


def retry_sync(
    func: Callable[..., T],
    *,
    max_retries: int = 2,
    base_delay: float = 0.5,
    retriable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[..., T]:
    """Wrap a sync callable with retry-with-backoff semantics."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except retriable_exceptions as exc:  # noqa: BLE001
                last_exc = exc
                if attempt == max_retries or not _is_retriable(exc):
                    break
                sleep_for = _delay(attempt, base_delay)
                logger.warning(
                    "Retrying %s after error (attempt %s/%s): %s",
                    func.__name__, attempt + 1, max_retries, exc,
                )
                time.sleep(sleep_for)
        assert last_exc is not None
        raise last_exc

    return wrapper


def retry_async(
    func: Callable[..., Awaitable[T]],
    *,
    max_retries: int = 2,
    base_delay: float = 0.5,
    retriable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[..., Awaitable[T]]:
    """Wrap an async callable with retry-with-backoff semantics."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except retriable_exceptions as exc:  # noqa: BLE001
                last_exc = exc
                if attempt == max_retries or not _is_retriable(exc):
                    break
                sleep_for = _delay(attempt, base_delay)
                logger.warning(
                    "Retrying %s after error (attempt %s/%s): %s",
                    func.__name__, attempt + 1, max_retries, exc,
                )
                await asyncio.sleep(sleep_for)
        assert last_exc is not None
        raise last_exc

    return wrapper
