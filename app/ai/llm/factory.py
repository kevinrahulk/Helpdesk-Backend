"""
Provider factory.

This is the single place that knows how to turn a provider *name*
(a plain string coming from config/env) into a concrete LangChain chat
or embeddings model. Everything above this layer (nodes, graphs,
services) only ever talks to the `BaseChatModel` / `Embeddings`
interfaces — never to a provider-specific class — so switching
providers is a one-line config change, not a code change.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

from app.ai.config import AISettings, LLMProviderName, get_ai_settings

# pyrefly: ignore [missing-import]
from langchain_core.language_models.chat_models import BaseChatModel
# pyrefly: ignore [missing-import]
from langchain_core.embeddings import Embeddings


_CHAT_BUILDERS: dict[LLMProviderName, str] = {
    "openai": "app.ai.llm.providers.openai_provider",
    "gemini": "app.ai.llm.providers.gemini_provider",
    "anthropic": "app.ai.llm.providers.anthropic_provider",
    "ollama": "app.ai.llm.providers.ollama_provider",
    "azure_openai": "app.ai.llm.providers.azure_openai_provider",
}


def _import_builder(module_path: str, func_name: str) -> Callable[[AISettings], Any]:
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, func_name)


@lru_cache(maxsize=16)
def get_chat_model(provider: LLMProviderName | None = None) -> BaseChatModel:
    """
    Return a configured chat model for `provider` (or the configured
    primary provider if omitted). Cached per-provider for the lifetime
    of the process so we don't rebuild HTTP clients on every request.
    """
    settings = get_ai_settings()
    provider = provider or settings.AI_PRIMARY_PROVIDER
    module_path = _CHAT_BUILDERS.get(provider)
    if module_path is None:
        raise ValueError(f"Unknown LLM provider: {provider!r}")
    builder = _import_builder(module_path, "build_chat_model")
    return builder(settings)


@lru_cache(maxsize=8)
def get_embeddings_model(provider: LLMProviderName | None = None) -> Embeddings:
    settings = get_ai_settings()
    provider = provider or settings.EMBEDDING_PROVIDER
    module_path = _CHAT_BUILDERS.get(provider)
    if module_path is None:
        raise ValueError(f"Unknown embeddings provider: {provider!r}")
    builder = _import_builder(module_path, "build_embeddings_model")
    if not hasattr(__import__(module_path, fromlist=["build_embeddings_model"]), "build_embeddings_model"):
        raise ValueError(f"Provider {provider!r} does not support embeddings.")
    return builder(settings)
