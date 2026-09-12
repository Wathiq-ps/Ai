import asyncio
import math

from openai import AsyncOpenAI

from app.providers.base import EmbeddingProvider, LLMProvider


class OpenAICompatibleLLMProvider(LLMProvider):
    """Works against any OpenAI-Chat-Completions-compatible endpoint —
    OpenRouter today (deepseek/deepseek-v4-pro), swap base_url/model to change."""

    def __init__(self, client: AsyncOpenAI, model: str):
        self._client = client
        self._model = model

    async def chat(
        self, system: str, user: str, *, json_mode: bool = False, max_tokens: int | None = None
    ) -> str:
        kwargs: dict = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )
        # ponytail: DeepSeek's json_object mode has a known issue where it
        # occasionally returns empty content instead of raising — callers
        # that json_mode=True must treat "" as an invalid/retryable result,
        # not assume a non-exception response is usable.
        return response.choices[0].message.content or ""


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Works against any OpenAI-Embeddings-compatible endpoint — OpenRouter
    today (nvidia/nemotron-3-embed-1b:free). `encoding_format="float"` is
    required: the SDK defaults to base64, which OpenRouter's Nvidia backend
    rejects with a 400.

    nemotron-3-embed-1b refuses any `dimensions` but its native 2048
    ("dimensions must be one of 2048"), so when `native_dimensions` exceeds the
    target we ask for native and truncate here instead. Measured on Arabic legal
    text, cutting 2048 -> 1536 keeps the model's separation (query~relevant
    0.745 -> 0.761, query~unrelated 0.149 -> 0.154), i.e. it is Matryoshka-style
    ordered — re-measure before trusting this with a model that is not.
    Vectors are renormalised so a truncated vector stays unit length and its
    `<=>` scores stay comparable with untruncated ones.
    """

    def __init__(self, client: AsyncOpenAI, model: str, dimensions: int, native_dimensions: int | None = None):
        self._client = client
        self._model = model
        self.dimensions = dimensions
        self._request_dimensions = native_dimensions or dimensions

    # ponytail: fixed batch size, sequential — a full-corpus reindex is ~1700
    # chunks and runs as a background job, so throughput does not matter yet.
    # Sized against the free tier's *request* quota (50/day), not latency: 64
    # would need 27 requests per rebuild, 256 needs 7. Ceiling: if a provider
    # caps inputs per request below this, embed() starts 400-ing — lower it
    # (the first full run on a fresh quota is what proves the number).
    BATCH_SIZE = 256

    # OpenRouter's free tier allows 20 requests/minute across free models and
    # answers 429 past that. A full-corpus reindex is ~27 batches, so this is
    # hit every time: wait out the window rather than failing the rebuild.
    RATE_LIMIT_WAIT_SECONDS = 20
    RATE_LIMIT_RETRIES = 6

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            response = await self._create_with_retry(texts[start : start + self.BATCH_SIZE])
            # The API may return items out of order; index is authoritative.
            for item in sorted(response.data, key=lambda d: d.index):
                vectors.append(self._fit(item.embedding))
        return vectors

    async def _create_with_retry(self, batch: list[str]):
        from openai import RateLimitError

        for attempt in range(self.RATE_LIMIT_RETRIES):
            try:
                return await self._client.embeddings.create(
                    model=self._model,
                    input=batch,
                    dimensions=self._request_dimensions,
                    encoding_format="float",
                )
            except RateLimitError:
                if attempt == self.RATE_LIMIT_RETRIES - 1:
                    raise
                await asyncio.sleep(self.RATE_LIMIT_WAIT_SECONDS)

    def _fit(self, vector: list[float]) -> list[float]:
        if len(vector) <= self.dimensions:
            return vector
        head = vector[: self.dimensions]
        norm = math.sqrt(sum(x * x for x in head))
        return [x / norm for x in head] if norm else head
