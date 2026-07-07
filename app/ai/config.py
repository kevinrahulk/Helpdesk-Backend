from __future__ import annotations
from functools import lru_cache
from typing import Literal
# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings,SettingsConfigDict
# pyrefly: ignore [missing-import]
from pydantic import Field, model_validator

LLMProviderName = Literal["openai", "gemini", "groq"]

# Providers that don't need an API key to build a chat model (local/self-hosted).
_NO_KEY_REQUIRED: set[str] = set()

class AISettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Primary Provider
    AI_PRIMARY_PROVIDER: LLMProviderName = "groq"
    # Fallback Provider
    AI_FALLBACK_PROVIDER: LLMProviderName | None = "openai"

    # Per-provider model names
    OPENAI_MODEL: str = "gpt-oss-20b"
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_BASE_URL: str = "https://openrouter.ai/api/v1"

    GEMINI_MODEL: str = "gemini-2.5-flash"
    GOOGLE_API_KEY: str =  Field(default="")

    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_API_KEY: str = Field(default="")

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
            "groq": ("GROQ_API_KEY", self.GROQ_API_KEY),
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
