"""Sprint 6 — analyze_contract against the real DB, real embedder, real LLM.

Same deal as tests/test_generate_contract_live.py: no mocks, small real API
spend per run, nothing written. Feeds a deliberately flawed contract (no
dispute-resolution clause, no price, vague duration) and asserts the agent
comes back with grounded findings and a score — quality of the legal judgment
is not asserted, only that the chain works and BR-25 holds.

    WATHIQ_DB_TESTS=1 uv run pytest tests/test_analyze_contract_live.py
"""

import os

import asyncpg
import pytest
from pgvector.asyncpg import register_vector

from app.analyze_contract import analyze_contract
from app.config import settings
from app.providers import get_embedding_provider, get_llm_provider

pytestmark = pytest.mark.skipif(
    not settings.database_url or not settings.deepseek_api_key or not settings.openrouter_api_key
    or os.environ.get("WATHIQ_DB_TESTS") != "1",
    reason="integration test: needs DATABASE_URL + DEEPSEEK_API_KEY + OPENROUTER_API_KEY + WATHIQ_DB_TESTS=1",
)

FLAWED_CONTRACT = """عقد إيجار

الطرف الأول: أحمد، الطرف الثاني: سارة.
يؤجر الطرف الأول الشقة الكائنة في مدينة غزة إلى الطرف الثاني لمدة مناسبة.
يلتزم الطرف الثاني بدفع الأجرة عند الطلب.
"""


def test_analyze_contract_end_to_end_against_live_infra():
    import asyncio

    async def scenario():
        pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2, init=register_vector)
        try:
            async with pool.acquire() as conn:
                jurisdiction_id = await conn.fetchval("select id from app.jurisdictions limit 1")
            assert jurisdiction_id is not None, "no jurisdiction seeded — see Back-end#5"

            result = await analyze_contract(
                pool,
                get_llm_provider(),
                get_embedding_provider(),
                jurisdiction_id=jurisdiction_id,
                content=FLAWED_CONTRACT,
                contract_type="rent",
            )

            assert result.findings, "a contract this thin should produce findings"
            assert all(f.citations for f in result.findings), "BR-25: every finding must be grounded"
            assert 0 <= result.risk_score <= 100
            assert result.summary_ar and result.summary_en
            assert result.kb_version_id is not None
        finally:
            await pool.close()

    asyncio.run(scenario())
