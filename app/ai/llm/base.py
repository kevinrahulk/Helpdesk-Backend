"""
`StructuredLLM` is the ONE interface every AI node talks to. It hides:

  * which provider is being used (OpenAI, Gemini, Groq)
  * retries with exponential backoff
  * automatic fallback to a secondary provider on failure
  * response caching (optional, keyed by prompt content)
  * structured-output parsing into a Pydantic model

Nodes never import `langchain_openai`, `langchain_anthropic`, etc.
directly — they only import `StructuredLLM` and a Pydantic output model.
This is what makes "switch providers without rewriting the graph"
actually true.
"""

from __future__ import annotations

import logging
from typing import Type, TypeVar

# pyrefly: ignore [missing-import]
from pydantic import BaseModel

from app.ai.config import AISettings, LLMProviderName, get_ai_settings
from app.ai.llm.factory import get_chat_model
from app.ai.tools.cache import ai_cache, make_cache_key
from app.ai.tools.retry import retry_async, retry_sync

logger = logging.getLogger("app.ai.llm")

TOutput = TypeVar("TOutput", bound=BaseModel)


class LLMInvocationError(RuntimeError):
    """Raised when both the primary and fallback provider fail."""


class StructuredLLM:
    """
    Thin, provider-agnostic facade over a LangChain chat model that
    always returns a validated Pydantic object.
    """

    def __init__(self, settings: AISettings | None = None) -> None:
        self._settings = settings or get_ai_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def invoke_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_model: Type[TOutput],
        node_name: str,
        use_cache: bool = True,
    ) -> TOutput:
        """Synchronous structured call with retry + fallback + caching."""
        cache_key = self._cache_key(node_name, system_prompt, user_prompt, output_model)
        if use_cache and self._settings.AI_ENABLE_CACHE:
            cached = ai_cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for node=%s", node_name)
                return cached

        def _call_provider(provider: LLMProviderName) -> TOutput:
            kwargs = {}
            if provider == "groq":
                kwargs["method"] = "function_calling"
            model = get_chat_model(provider).with_structured_output(output_model, **kwargs)
            return model.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

        result = self._invoke_with_fallback_sync(node_name, _call_provider)

        if use_cache and self._settings.AI_ENABLE_CACHE:
            ai_cache.set(cache_key, result, self._settings.AI_CACHE_TTL_SECONDS)
        return result

    async def ainvoke_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_model: Type[TOutput],
        node_name: str,
        use_cache: bool = True,
    ) -> TOutput:
        """Async structured call with retry + fallback + caching."""
        cache_key = self._cache_key(node_name, system_prompt, user_prompt, output_model)
        if use_cache and self._settings.AI_ENABLE_CACHE:
            cached = ai_cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for node=%s", node_name)
                return cached

        async def _call_provider(provider: LLMProviderName) -> TOutput:
            kwargs = {}
            if provider == "groq":
                kwargs["method"] = "function_calling"
            model = get_chat_model(provider).with_structured_output(output_model, **kwargs)
            return await model.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

        result = await self._invoke_with_fallback_async(node_name, _call_provider)

        if use_cache and self._settings.AI_ENABLE_CACHE:
            ai_cache.set(cache_key, result, self._settings.AI_CACHE_TTL_SECONDS)
        return result

    # ------------------------------------------------------------------
    # Internal — retry + fallback orchestration
    # ------------------------------------------------------------------

    def _invoke_with_fallback_sync(self, node_name, call_provider):
        primary = self._settings.AI_PRIMARY_PROVIDER
        fallback = self._settings.AI_FALLBACK_PROVIDER

        retriable = retry_sync(
            call_provider,
            max_retries=self._settings.AI_MAX_RETRIES,
            base_delay=self._settings.AI_RETRY_BASE_DELAY_SECONDS,
        )
        try:
            return retriable(primary)
        except Exception as primary_exc:  # noqa: BLE001
            logger.warning("Primary provider %s failed for node=%s: %s", primary, node_name, primary_exc)
            if not fallback or fallback == primary:
                raise LLMInvocationError(
                    f"Node '{node_name}' failed on provider '{primary}' with no fallback configured."
                ) from primary_exc
            try:
                retriable_fallback = retry_sync(
                    call_provider,
                    max_retries=self._settings.AI_MAX_RETRIES,
                    base_delay=self._settings.AI_RETRY_BASE_DELAY_SECONDS,
                )
                return retriable_fallback(fallback)
            except Exception as fallback_exc:  # noqa: BLE001
                raise LLMInvocationError(
                    f"Node '{node_name}' failed on both '{primary}' and fallback '{fallback}'."
                ) from fallback_exc

    async def _invoke_with_fallback_async(self, node_name, call_provider):
        primary = self._settings.AI_PRIMARY_PROVIDER
        fallback = self._settings.AI_FALLBACK_PROVIDER

        retriable = retry_async(
            call_provider,
            max_retries=self._settings.AI_MAX_RETRIES,
            base_delay=self._settings.AI_RETRY_BASE_DELAY_SECONDS,
        )
        try:
            return await retriable(primary)
        except Exception as primary_exc:  # noqa: BLE001
            logger.warning("Primary provider %s failed for node=%s: %s", primary, node_name, primary_exc)
            if not fallback or fallback == primary:
                raise LLMInvocationError(
                    f"Node '{node_name}' failed on provider '{primary}' with no fallback configured."
                ) from primary_exc
            try:
                retriable_fallback = retry_async(
                    call_provider,
                    max_retries=self._settings.AI_MAX_RETRIES,
                    base_delay=self._settings.AI_RETRY_BASE_DELAY_SECONDS,
                )
                return await retriable_fallback(fallback)
            except Exception as fallback_exc:  # noqa: BLE001
                raise LLMInvocationError(
                    f"Node '{node_name}' failed on both '{primary}' and fallback '{fallback}'."
                ) from fallback_exc

    @staticmethod
    def _cache_key(node_name: str, system_prompt: str, user_prompt: str, output_model: Type[BaseModel]) -> str:
        return make_cache_key(node_name, output_model.__name__, system_prompt, user_prompt)
