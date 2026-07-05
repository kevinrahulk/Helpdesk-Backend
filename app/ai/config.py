"""
AI subsystem configuration.

Kept separate from `app.config.Settings` so the AI layer can be reasoned
about (and reconfigured) independently of the rest of the application.
All values are overridable via environment variables / `.env`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings,SettingsConfigDict
# pyrefly: ignore [missing-import]
from pydantic import Field, model_validator

LLMProviderName = Literal["openai", "gemini", "anthropic", "ollama", "azure_openai"]

# Providers that don't need an API key to build a chat model (local/self-hosted).
_NO_KEY_REQUIRED: set[str] = {"ollama"}


class AISettings(BaseSettings):
    """Configuration for the LangGraph AI orchestration layer.

    SECURITY: no API keys have defaults here. Every provider key MUST be
    supplied via the environment (`.env` locally, a secrets manager in
    prod) or `AISettings()` raises `ValueError` at instantiation time —
    see `_validate_required_keys` below. This is intentional: silently
    falling back to an empty/dead key means every AI call fails at
    request time with a confusing provider error instead of failing
    loudly at startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Provider selection — switching providers requires changing ONLY
    # these values (see app.ai.llm.factory.get_chat_model).
    # ------------------------------------------------------------------
    AI_PRIMARY_PROVIDER: LLMProviderName = "openai"
    # A real fallback is configured by default so a single provider
    # outage doesn't zero out every AI feature. Set equal to
    # AI_PRIMARY_PROVIDER (or override via env) to disable fallback.
    AI_FALLBACK_PROVIDER: LLMProviderName | None = "gemini"

    # Per-provider model names
    OPENAI_MODEL: str = "gpt-oss-20b"
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_BASE_URL: str = "https://openrouter.ai/api/v1"

    GEMINI_MODEL: str = "gemini-2.5-flash"
    GOOGLE_API_KEY: str =  Field(default="")

    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_API_KEY: str = ""

    OLLAMA_MODEL: str = "llama3.1"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o-mini"
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"

    # Embeddings (used for similar-ticket vector search)
    EMBEDDING_PROVIDER: LLMProviderName = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    # ------------------------------------------------------------------
    # Execution behaviour
    # ------------------------------------------------------------------
    AI_REQUEST_TIMEOUT_SECONDS: float = 20.0
    AI_MAX_RETRIES: int = 2
    AI_RETRY_BASE_DELAY_SECONDS: float = 0.5
    AI_TEMPERATURE: float = 0.2
    # Explicit output token cap so providers (e.g. OpenRouter) don't have to
    # assume worst-case max_tokens when estimating whether we can afford the call.
    AI_MAX_TOKENS: int = 1536

    # Confidence threshold below which a ticket is flagged for human review
    AI_LOW_CONFIDENCE_THRESHOLD: float = 0.55

    # Feature flags — allow disabling pieces without touching graph code
    AI_ENABLE_SIMILAR_TICKETS: bool = True
    AI_ENABLE_VECTOR_SEARCH: bool = True
    AI_ENABLE_CACHE: bool = True
    AI_CACHE_TTL_SECONDS: int = 300

    # Similar ticket search
    AI_SIMILAR_TICKETS_TOP_K: int = 5
    AI_SIMILAR_TICKETS_MIN_SCORE: float = 0.70

    # Rate limiting (token-bucket per-process; swap for Redis in a multi-worker deploy)
    AI_RATE_LIMIT_PER_MINUTE: int = 60



    # ------------------------------------------------------------------
    # Fail loudly at startup instead of silently using a dead/empty key.
    # ------------------------------------------------------------------
    def _key_for_provider(self, provider: str) -> tuple[str, str] | None:
        """Return (env_var_name, value) for the API key `provider` needs,
        or None if that provider doesn't require one."""
        if provider in _NO_KEY_REQUIRED:
            return None
        mapping = {
            "openai": ("OPENAI_API_KEY", self.OPENAI_API_KEY),
            "gemini": ("GOOGLE_API_KEY", self.GOOGLE_API_KEY),
            "anthropic": ("ANTHROPIC_API_KEY", self.ANTHROPIC_API_KEY),
            "azure_openai": ("AZURE_OPENAI_API_KEY", self.AZURE_OPENAI_API_KEY),
        }
        return mapping.get(provider)

    @model_validator(mode="after")
    def _validate_required_keys(self) -> "AISettings":
        missing: list[str] = []

        for provider in {self.AI_PRIMARY_PROVIDER, self.EMBEDDING_PROVIDER}:
            key = self._key_for_provider(provider)
            if key and not key[1]:
                missing.append(f"{key[0]} (required for provider {provider!r})")

        if self.AI_FALLBACK_PROVIDER and self.AI_FALLBACK_PROVIDER != self.AI_PRIMARY_PROVIDER:
            key = self._key_for_provider(self.AI_FALLBACK_PROVIDER)
            if key and not key[1]:
                missing.append(f"{key[0]} (required for fallback provider {self.AI_FALLBACK_PROVIDER!r})")

        if self.AI_PRIMARY_PROVIDER == "azure_openai" or self.EMBEDDING_PROVIDER == "azure_openai":
            if not self.AZURE_OPENAI_ENDPOINT:
                missing.append("AZURE_OPENAI_ENDPOINT (required for provider 'azure_openai')")

        if missing:
            raise ValueError(
                "Missing required AI provider configuration: "
                + "; ".join(missing)
                + ". Set these in your environment or .env file — see .env.example. "
                "Refusing to start with an unset key rather than silently failing every AI call."
            )
        return self


@lru_cache()
def get_ai_settings() -> AISettings:
    return AISettings()
