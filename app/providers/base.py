from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, system: str, user: str) -> str:
        """Return the model's text response for a single-turn chat call."""


class EmbeddingProvider(ABC):
    dimensions: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, same order."""


class RerankProvider(ABC):
    @abstractmethod
    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        """Return (original_index, relevance_score) pairs, sorted by score desc."""
