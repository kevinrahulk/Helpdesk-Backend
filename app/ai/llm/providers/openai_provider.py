"""OpenAI provider — chat model and embeddings model builders."""

from __future__ import annotations

from app.ai.config import AISettings


def build_chat_model(settings: AISettings):
    # pyrefly: ignore [missing-import]
    from langchain_openai import ChatOpenAI

    import logging
    logger = logging.getLogger("app.ai.llm.providers.openai_provider")
    logger.debug(
        "Building OpenAI chat model: model=%s base_url=%s api_key_set=%s",
        settings.OPENAI_MODEL, settings.OPENAI_BASE_URL, bool(settings.OPENAI_API_KEY),
    )

    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY or None,
        base_url=settings.OPENAI_BASE_URL,
        temperature=settings.AI_TEMPERATURE,
        timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
        max_tokens=settings.AI_MAX_TOKENS,  # explicit cap so OpenRouter/OpenAI don't assume worst-case
        max_retries=0,  # retries are handled by app.ai.llm.base.StructuredLLM
    )


def build_embeddings_model(settings: AISettings):
    # pyrefly: ignore [missing-import]
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY or None,
        base_url=settings.OPENAI_BASE_URL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )
