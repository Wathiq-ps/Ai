from openai import AsyncOpenAI

from app.providers.base import EmbeddingProvider, LLMProvider


class OpenAICompatibleLLMProvider(LLMProvider):
    """Works against any OpenAI-Chat-Completions-compatible endpoint —
    OpenRouter today (deepseek/deepseek-v4-pro), swap base_url/model to change."""

    def __init__(self, client: AsyncOpenAI, model: str):
        self._client = client
        self._model = model

    async def chat(self, system: str, user: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Works against any OpenAI-Embeddings-compatible endpoint — OpenRouter
    today (nvidia/llama-nemotron-embed-vl-1b-v2:free, truncated to 1536 via
    `dimensions`). `encoding_format="float"` is required: the SDK defaults to
    base64, which OpenRouter's Nvidia backend rejects with a 400."""

    def __init__(self, client: AsyncOpenAI, model: str, dimensions: int):
        self._client = client
        self._model = model
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._model, input=texts, dimensions=self.dimensions, encoding_format="float"
        )
        return [item.embedding for item in response.data]
