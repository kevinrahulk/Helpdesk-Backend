"""Groq provider using langchain-openai to avoid external dependency."""

from __future__ import annotations

from app.ai.config import AISettings


def build_chat_model(settings: AISettings):
    # pyrefly: ignore [missing-import]
    from langchain_openai import ChatOpenAI

    import logging
    logger = logging.getLogger("app.ai.llm.providers.groq_provider")
    logger.debug(
        "Building Groq chat model: model=%s base_url=https://api.groq.com/openai/v1 api_key_set=%s",
        settings.GROQ_MODEL, bool(settings.GROQ_API_KEY),
    )

    return ChatOpenAI(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY or None,
        base_url="https://api.groq.com/openai/v1",
        temperature=settings.AI_TEMPERATURE,
        timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
        max_tokens=settings.AI_MAX_TOKENS,
        max_retries=0,  # retries are handled by app.ai.llm.base.StructuredLLM
    )


def build_embeddings_model(settings: AISettings):
    raise NotImplementedError("Groq does not provide an embeddings endpoint. Please use 'openai' as the EMBEDDING_PROVIDER.")
