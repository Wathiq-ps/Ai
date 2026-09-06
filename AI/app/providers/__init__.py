from app.config import settings
from app.providers.base import EmbeddingProvider, LLMProvider, RerankProvider
from app.providers.fake import FakeEmbeddingProvider, FakeLLMProvider, FakeRerankProvider

__all__ = [
    "get_llm_provider",
    "get_embedding_provider",
    "get_rerank_provider",
    "LLMProvider",
    "EmbeddingProvider",
    "RerankProvider",
]


def get_llm_provider() -> LLMProvider:
    if not settings.deepseek_api_key:
        return FakeLLMProvider()
    from openai import AsyncOpenAI

    from app.providers.openai_compatible import OpenAICompatibleLLMProvider

    client = AsyncOpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    return OpenAICompatibleLLMProvider(client, settings.chat_model)


def get_embedding_provider() -> EmbeddingProvider:
    if not settings.openrouter_api_key:
        return FakeEmbeddingProvider(settings.embedding_dimensions)
    from openai import AsyncOpenAI

    from app.providers.openai_compatible import OpenAICompatibleEmbeddingProvider

    client = AsyncOpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)
    return OpenAICompatibleEmbeddingProvider(client, settings.embedding_model, settings.embedding_dimensions)


def get_rerank_provider() -> RerankProvider:
    if not settings.openrouter_api_key:
        return FakeRerankProvider()
    import httpx

    from app.providers.openrouter_rerank import OpenRouterRerankProvider

    client = httpx.AsyncClient(
        base_url=settings.openrouter_base_url,
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
    )
    return OpenRouterRerankProvider(client, settings.rerank_model)
