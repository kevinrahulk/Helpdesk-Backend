"""Thin retry-wrapped helper around the configured embeddings provider."""

from __future__ import annotations

import logging

from app.ai.config import get_ai_settings
from app.ai.llm.factory import get_embeddings_model
from app.ai.tools.retry import retry_async, retry_sync

logger = logging.getLogger("app.ai.embeddings")


def embed_text(text: str) -> list[float]:
    settings = get_ai_settings()
    model = get_embeddings_model(settings.EMBEDDING_PROVIDER)

    fn = retry_sync(
        model.embed_query,
        max_retries=settings.AI_MAX_RETRIES,
        base_delay=settings.AI_RETRY_BASE_DELAY_SECONDS,
    )
    return fn(text)


async def aembed_text(text: str) -> list[float]:
    settings = get_ai_settings()
    model = get_embeddings_model(settings.EMBEDDING_PROVIDER)

    fn = retry_async(
        model.aembed_query,
        max_retries=settings.AI_MAX_RETRIES,
        base_delay=settings.AI_RETRY_BASE_DELAY_SECONDS,
    )
    return await fn(text)
