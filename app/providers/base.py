from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self, system: str, user: str, *, json_mode: bool = False, max_tokens: int | None = None
    ) -> str:
        """Return the model's text response for a single-turn chat call.

        json_mode requests the provider's structured-JSON output mode (e.g.
        OpenAI-compatible `response_format={"type": "json_object"}`) where
        supported — callers must still validate the result, this only
        improves the odds. The prompt itself must still mention "json" and
        show the desired shape (DeepSeek requires this)."""


class EmbeddingProvider(ABC):
    dimensions: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, same order."""


class RerankProvider(ABC):
    @abstractmethod
    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        """Return (original_index, relevance_score) pairs, sorted by score desc."""
