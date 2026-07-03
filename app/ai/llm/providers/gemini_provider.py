"""Google Gemini provider — chat model and embeddings model builders."""

from __future__ import annotations

from app.ai.config import AISettings


def build_chat_model(settings: AISettings):
    # pyrefly: ignore [missing-import]
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY or None,
        temperature=settings.AI_TEMPERATURE,
        timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )


def build_embeddings_model(settings: AISettings):
    # pyrefly: ignore [missing-import]
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY or None,
    )
