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


# Exception class names (across the OpenAI/Anthropic/Google/Azure SDKs
# that langchain wraps) that mean "this request is fundamentally
# invalid" rather than "this failed transiently" — a bad API key, a
# malformed request, a missing resource, etc. Retrying these just
# burns the full backoff delay for a result that will never change,
# and doubles that cost again on the fallback provider. Matched by
# name (not `isinstance`) so this doesn't need every provider SDK
# imported just to classify its errors.
_NON_RETRIABLE_NAMES = {
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "BadRequestError",
    "InvalidRequestError",
    "UnprocessableEntityError",
    "PermissionError",
}

# HTTP status codes that mean the same thing when an exception exposes
# one (most provider SDKs set `.status_code` or `.response.status_code`).
# 402 (Payment Required) is included because providers like OpenRouter use
# it for insufficient credit — retrying won't help until the account is
# topped up (or the request is made cheaper, e.g. via a lower max_tokens),
# and burning retries here just delays falling back for no benefit.
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
