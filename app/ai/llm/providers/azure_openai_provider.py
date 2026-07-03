"""Azure OpenAI provider — chat model and embeddings model builders."""

from __future__ import annotations

from app.ai.config import AISettings


def build_chat_model(settings: AISettings):
    # pyrefly: ignore [missing-import]
    from langchain_openai import AzureChatOpenAI

    return AzureChatOpenAI(
        azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY or None,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        temperature=settings.AI_TEMPERATURE,
        timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )


def build_embeddings_model(settings: AISettings):
    # pyrefly: ignore [missing-import]
    from langchain_openai import AzureOpenAIEmbeddings

    return AzureOpenAIEmbeddings(
        azure_deployment=settings.EMBEDDING_MODEL,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY or None,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )
