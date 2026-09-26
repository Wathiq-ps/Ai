import asyncio
from types import SimpleNamespace

import pytest

from app.providers.fake import FakeLLMProvider, FakeRerankProvider
from app.providers.openai_compatible import (
    LLMOutputTruncated,
    OpenAICompatibleLLMProvider,
)
from app.usage import JobUsage, current_usage


def _chat_response(finish_reason="stop", content='{"ok":1}', prompt_tokens=0, completion_tokens=0):
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish_reason, message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=4096),
        ),
    )


def _llm(*responses) -> OpenAICompatibleLLMProvider:
    """The real provider over a stub client that hands out `responses` in call order."""
    queue = list(responses)

    class _StubCompletions:
        async def create(self, **kwargs):
            return queue.pop(0)

    client = SimpleNamespace(chat=SimpleNamespace(completions=_StubCompletions()))
    return OpenAICompatibleLLMProvider(client, "deepseek-v4-flash")


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
    import math

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
    texts = [f"t{i}" for i in range(provider.BATCH_SIZE + 6)]

    vectors = asyncio.run(provider.embed(texts))

    assert [len(batch) for batch in calls] == [provider.BATCH_SIZE, 6]
    assert len(vectors) == len(texts)
    assert all(len(v) == 1536 for v in vectors)
    assert math.isclose(math.sqrt(sum(x * x for x in vectors[0])), 1.0, rel_tol=1e-6)


def test_llm_provider_raises_instead_of_returning_a_truncated_reply():
    """`max_tokens` on a reasoning model budgets reasoning *and* output, so a
    tight cap can return empty or half-written content with
    finish_reason='length'. Retrying that at the same cap can only fail again,
    and the JSON parser then reports it as malformed JSON — which is the wrong
    thing to go looking at. Measured: deepseek-v4-flash spent all 4096 tokens
    on reasoning and emitted no content at all."""
    with pytest.raises(LLMOutputTruncated) as excinfo:
        asyncio.run(_llm(_chat_response("length", "")).chat("s", "u", json_mode=True, max_tokens=4096))
    assert "4096" in str(excinfo.value)

    # A normal reply is untouched, and empty content that did NOT hit the cap
    # still comes back as "" for the caller's JSON-repair loop to retry.
    assert asyncio.run(_llm(_chat_response("stop", '{"ok":1}')).chat("s", "u")) == '{"ok":1}'
    assert asyncio.run(_llm(_chat_response("stop", None)).chat("s", "u")) == ""


def test_deepseek_provider_names_flash_and_turns_thinking_off(monkeypatch):
    """deepseek-flash thinks by default, and thinking is what blew NFR-1.1's
    60s budget before (config.py). Every call must carry the switch."""
    from app import providers

    monkeypatch.setattr(providers.settings, "deepseek_api_key", "test-key")
    sent = []

    class _StubCompletions:
        async def create(self, **kwargs):
            sent.append(kwargs)
            return _chat_response()

    llm = providers.get_llm_provider()
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=_StubCompletions()))
    asyncio.run(llm.chat("s", "u", json_mode=True))

    assert sent[0]["model"] == providers.settings.chat_model  # a local .env may override
    assert type(providers.settings).model_fields["chat_model"].default == "deepseek-flash"
    assert sent[0]["extra_body"] == {"thinking": {"type": "disabled"}}


def test_llm_provider_adds_every_calls_tokens_to_the_current_job():
    """This sum is the callback's `usage`. A truncated reply is billed like
    any other, so it counts even though chat() raises on it."""
    llm = _llm(
        _chat_response(prompt_tokens=1200, completion_tokens=300),
        _chat_response("length", "", prompt_tokens=1200, completion_tokens=4096),
    )
    usage = JobUsage(job_id="j")

    async def run():
        current_usage.set(usage)
        await llm.chat("s", "u")
        with pytest.raises(LLMOutputTruncated):
            await llm.chat("s", "u", max_tokens=4096)
        await FakeLLMProvider().chat("s", "u")  # spends nothing, reports nothing

    asyncio.run(run())

    assert (usage.prompt_tokens, usage.completion_tokens) == (2400, 4396)
