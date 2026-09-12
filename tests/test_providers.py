import asyncio

from app.providers.fake import FakeRerankProvider


def test_fake_rerank_orders_by_query_word_overlap():
    provider = FakeRerankProvider()
    results = asyncio.run(
        provider.rerank(
            query="capital of France",
            documents=["Paris is the capital of France", "Berlin is a city in Germany"],
            top_n=2,
        )
    )
    assert [index for index, _ in results] == [0, 1]
    assert results[0][1] > results[1][1]


def test_fake_rerank_respects_top_n():
    provider = FakeRerankProvider()
    results = asyncio.run(
        provider.rerank(query="capital of France", documents=["a", "b", "c"], top_n=1)
    )
    assert len(results) == 1


def test_embedding_provider_batches_truncates_and_keeps_input_order():
    """Batching + the 2048->1536 truncation, against a stub client — no network."""
    import asyncio
    import math
    from types import SimpleNamespace

    from app.providers.openai_compatible import OpenAICompatibleEmbeddingProvider

    calls: list[list[str]] = []

    class _StubEmbeddings:
        async def create(self, *, model, input, dimensions, encoding_format):
            calls.append(list(input))
            # Returned out of order on purpose: `index` is what must be trusted.
            data = [
                SimpleNamespace(index=i, embedding=[float(hash(text) % 7 + 1)] * dimensions)
                for i, text in enumerate(input)
            ][::-1]
            return SimpleNamespace(data=data)

    provider = OpenAICompatibleEmbeddingProvider(
        SimpleNamespace(embeddings=_StubEmbeddings()), "m", 1536, native_dimensions=2048
    )
    texts = [f"t{i}" for i in range(70)]

    vectors = asyncio.run(provider.embed(texts))

    assert [len(batch) for batch in calls] == [64, 6]
    assert len(vectors) == 70
    assert all(len(v) == 1536 for v in vectors)
    assert math.isclose(math.sqrt(sum(x * x for x in vectors[0])), 1.0, rel_tol=1e-6)
