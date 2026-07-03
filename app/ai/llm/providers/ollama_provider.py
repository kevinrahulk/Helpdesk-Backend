"""Ollama (local) provider — chat model and embeddings model builders."""

from __future__ import annotations

from app.ai.config import AISettings


def build_chat_model(settings: AISettings):
    # pyrefly: ignore [missing-import]
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=settings.AI_TEMPERATURE,
    )


def build_embeddings_model(settings: AISettings):
    # pyrefly: ignore [missing-import]
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(
        model=settings.EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )
