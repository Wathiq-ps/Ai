"""Sprint 5 — generate_contract against the real DB, real embedder, real LLM.

No mocks anywhere in this file. This is the one place proving the whole
chain (retrieval -> DeepSeek json_mode -> citation grounding) actually works
outside the offline fakes in tests/test_generate_contract.py. It costs a
small amount of real API spend per run and does not clean anything up
(read-only against knowledge.*, no rows written) — see
tests/test_knowledge_integration.py for the write/cleanup pattern this
deliberately does not need.

    WATHIQ_DB_TESTS=1 uv run pytest tests/test_generate_contract_live.py

Today's corpus is thin (a handful of seed articles, see
SPRINT4_NEXT_STEPS.md item 6, still open) — this only asserts structural
correctness (all clause kinds present, real citations), not draft quality.
"""

import os

import asyncpg
import pytest
from pgvector.asyncpg import register_vector

from app.config import settings
from app.generate_contract import CLAUSE_KINDS, generate_contract
from app.providers import get_embedding_provider, get_llm_provider

pytestmark = pytest.mark.skipif(
    not settings.database_url or not settings.deepseek_api_key or not settings.openrouter_api_key
    or os.environ.get("WATHIQ_DB_TESTS") != "1",
    reason="integration test: needs DATABASE_URL + DEEPSEEK_API_KEY + OPENROUTER_API_KEY + WATHIQ_DB_TESTS=1",
)


def test_generate_contract_end_to_end_against_live_infra():
    import asyncio

    async def scenario():
        pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2, init=register_vector)
        try:
            async with pool.acquire() as conn:
                jurisdiction_id = await conn.fetchval("select id from app.jurisdictions limit 1")
            assert jurisdiction_id is not None, "no jurisdiction seeded — see Back-end#5"

            result = await generate_contract(
                pool,
                get_llm_provider(),
                get_embedding_provider(),
                jurisdiction_id=jurisdiction_id,
                contract_type="sale",
                parties=[{"role": "seller", "name": "Ahmad"}, {"role": "buyer", "name": "Sara"}],
                property={"address": "Gaza City", "type": "apartment"},
                language="ar",
            )

            assert {c.clause_kind for c in result.clauses} == set(CLAUSE_KINDS)
            assert all(c.content.strip() for c in result.clauses)
            assert result.citations, "a live draft with zero citations is ungrounded (BR-25)"
            assert result.kb_version_id is not None
            assert result.body
        finally:
            await pool.close()

    asyncio.run(scenario())
