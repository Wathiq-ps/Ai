import httpx

from app.providers.base import RerankProvider


class OpenRouterRerankProvider(RerankProvider):
    """Calls OpenRouter's dedicated /rerank endpoint — not OpenAI-Chat/Embeddings-shaped,
    so unlike the other providers this doesn't reuse the `openai` SDK client."""

    def __init__(self, client: httpx.AsyncClient, model: str):
        self._client = client
        self._model = model

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        response = await self._client.post(
            "/rerank",
            json={"model": self._model, "query": query, "documents": documents, "top_n": top_n},
        )
        response.raise_for_status()
        return [(r["index"], r["relevance_score"]) for r in response.json()["results"]]
