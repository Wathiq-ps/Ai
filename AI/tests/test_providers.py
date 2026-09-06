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
