"""Anthropic Claude provider — chat model builder.

Anthropic does not offer a first-party embeddings endpoint, so this
provider intentionally does not implement `build_embeddings_model`.
Configure `EMBEDDING_PROVIDER` to a different provider if you select
Anthropic as the primary/fallback chat provider.
"""

from __future__ import annotations

from app.ai.config import AISettings


def build_chat_model(settings: AISettings):
    # pyrefly: ignore [missing-import]
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=settings.ANTHROPIC_MODEL,
        api_key=settings.ANTHROPIC_API_KEY or None,
        temperature=settings.AI_TEMPERATURE,
        timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )
