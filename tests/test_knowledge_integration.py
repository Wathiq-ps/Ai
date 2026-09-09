"""Sprint 4 exit criteria 3-5, against a real Postgres.

These are the only tests that execute `app/knowledge.py`'s SQL — every other
test in the suite runs offline. Opt in with:

    WATHIQ_DB_TESTS=1 uv run pytest tests/test_knowledge_integration.py

Every row created here is tagged with a per-run prefix and deleted afterwards,
and the kb_version that was `active` before the run is restored — a rebuild
supersedes whatever was active for that jurisdiction, so without the restore
these tests would leave the database serving a test index.
"""

import asyncio
import contextlib
import os
import uuid
from datetime import date

import asyncpg
import pytest
from pgvector.asyncpg import register_vector

from app.config import settings
from app.knowledge import (
    DocumentForIndex,
    ingest_document,
    rebuild_kb_version,
    search,
)
from app.providers.base import EmbeddingProvider
from app.providers.fake import FakeEmbeddingProvider

pytestmark = pytest.mark.skipif(
    not settings.database_url or os.environ.get("WATHIQ_DB_TESTS") != "1",
    reason="integration test: needs a real DATABASE_URL and WATHIQ_DB_TESTS=1",
)

LAW_TEXT = (
    "المادة (1): يلتزم البائع بتسليم المبيع إلى المشتري.\n\n"
    "المادة (2): على المشتري دفع الثمن في الموعد المتفق عليه.\n\n"
    "المادة (3): يتحمل البائع نفقات التسليم ما لم يتفق على غير ذلك."
)
EXPECTED_CHUNKS = 3
EFFECTIVE_FROM = date(2020, 1, 1)

# search() drops anything scoring below min_score; fake vectors are arbitrary
# directions and routinely score negative, so integration tests must not rely
# on the 0.0 default to decide what is "found".
NO_SCORE_FLOOR = -1.0


class _FailingEmbeddingProvider(EmbeddingProvider):
    """Stands in for a provider outage partway through a rebuild."""

    dimensions = 1536

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding provider is down")


def _require_verifier(verifier_id):
    if verifier_id is None:
        pytest.skip(
            "no verified knowledge.sources row to borrow a verified_by from, and "
            "wathiq_ai cannot read app.users to find one"
        )


@contextlib.asynccontextmanager
async def _sandbox():
    """Pool + jurisdiction + a unique tag prefix, with full cleanup on exit."""
    pool = await asyncpg.create_pool(
        settings.database_url, min_size=1, max_size=2, init=register_vector
    )
    prefix = f"pytest-{uuid.uuid4().hex[:8]}-"
    like = f"{prefix}%"
    try:
        async with pool.acquire() as conn:
            # ponytail: the MVP has exactly one jurisdiction (Gaza). Pin this to
            # a specific `code` once West Bank is seeded as a second row.
            jurisdiction_id = await conn.fetchval("select id from app.jurisdictions limit 1")
            assert jurisdiction_id is not None, "no jurisdiction seeded — see Back-end#5"
            previously_active = await conn.fetchval(
                "select id from knowledge.kb_versions "
                "where jurisdiction_id = $1 and status = 'active'",
                jurisdiction_id,
            )
            # `sources_verified_complete` demands verified_by whenever
            # is_verified is true, and that column is a FK to app.users — which
            # `wathiq_ai` may not read. A verified source can therefore only be
            # built by borrowing a verifier that already exists in
            # knowledge.sources; see this module's docstring.
            verifier_id = await conn.fetchval(
                "select verified_by from knowledge.sources where verified_by is not null limit 1"
            )
        yield pool, jurisdiction_id, prefix, verifier_id
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "delete from knowledge.chunks where kb_version_id in "
                "(select id from knowledge.kb_versions where tag like $1)",
                like,
            )
            await conn.execute("delete from knowledge.kb_versions where tag like $1", like)
            await conn.execute("delete from knowledge.documents where title like $1", like)
            await conn.execute("delete from knowledge.sources where title_ar like $1", like)
            if previously_active is not None:
                await conn.execute(
                    "update knowledge.kb_versions set status = 'active' where id = $1",
                    previously_active,
                )
        await pool.close()


async def _seed_document(
    pool,
    jurisdiction_id,
    prefix,
    *,
    is_verified=True,
    verifier_id=None,
    effective_to=None,
) -> DocumentForIndex:
    """One source + one document, ready to be chunked into a kb_version."""
    async with pool.acquire() as conn:
        source_id = await conn.fetchval(
            """
            insert into knowledge.sources
                (jurisdiction_id, law_type, title_ar, publisher,
                 effective_from, effective_to, is_verified, verified_by, verified_at)
            values ($1, 'sale'::app.law_type, $2, 'pytest', $3, $4, $5, $6,
                    case when $5 then now() end)
            returning id
            """,
            jurisdiction_id,
            f"{prefix}source",
            EFFECTIVE_FROM,
            effective_to,
            is_verified,
            verifier_id if is_verified else None,
        )

    document_id = await ingest_document(
        pool, source_id=source_id, title=f"{prefix}document", raw_text=LAW_TEXT
    )

    return DocumentForIndex(
        document_id=document_id,
        jurisdiction_id=jurisdiction_id,
        law_type="sale",
        text=LAW_TEXT,
        effective_from=EFFECTIVE_FROM,
        effective_to=effective_to,
    )


async def _version_status(pool, kb_version_id) -> str:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "select status::text from knowledge.kb_versions where id = $1", kb_version_id
        )


def test_rebuild_then_search_returns_the_seeded_chunks():
    """Exit criterion 3: the round trip — seed, rebuild, retrieve."""

    async def scenario():
        async with _sandbox() as (pool, jurisdiction_id, prefix, verifier_id):
            _require_verifier(verifier_id)
            embedder = FakeEmbeddingProvider(settings.embedding_dimensions)
            document = await _seed_document(
                pool, jurisdiction_id, prefix, verifier_id=verifier_id
            )

            kb_version_id = await rebuild_kb_version(
                pool,
                embedder,
                jurisdiction_id=jurisdiction_id,
                tag=f"{prefix}v1",
                embedding_model="fake/deterministic",
                documents=[document],
            )

            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "select status::text as status, chunk_count "
                    "from knowledge.kb_versions where id = $1",
                    kb_version_id,
                )
            assert row["status"] == "active"
            assert row["chunk_count"] == EXPECTED_CHUNKS

            results = await search(
                pool,
                embedder,
                jurisdiction_id=jurisdiction_id,
                query="التزامات البائع",
                k=10,
                min_score=NO_SCORE_FLOOR,
            )
            assert len(results) == EXPECTED_CHUNKS
            assert {r.document_id for r in results} == {document.document_id}
            # The article anchor is the citation unit the product depends on.
            assert {r.article for r in results} == {"المادة (1)", "المادة (2)", "المادة (3)"}
            assert all(r.law_type == "sale" for r in results)

    asyncio.run(scenario())


def test_failed_build_leaves_the_previous_version_serving():
    """Exit criterion 4: fail closed. A broken rebuild must not take the
    knowledge base offline or serve a half-built index."""

    async def scenario():
        async with _sandbox() as (pool, jurisdiction_id, prefix, verifier_id):
            _require_verifier(verifier_id)
            embedder = FakeEmbeddingProvider(settings.embedding_dimensions)
            document = await _seed_document(
                pool, jurisdiction_id, prefix, verifier_id=verifier_id
            )

            good_version_id = await rebuild_kb_version(
                pool,
                embedder,
                jurisdiction_id=jurisdiction_id,
                tag=f"{prefix}good",
                embedding_model="fake/deterministic",
                documents=[document],
            )

            with pytest.raises(RuntimeError, match="embedding provider is down"):
                await rebuild_kb_version(
                    pool,
                    _FailingEmbeddingProvider(),
                    jurisdiction_id=jurisdiction_id,
                    tag=f"{prefix}broken",
                    embedding_model="fake/deterministic",
                    documents=[document],
                )

            async with pool.acquire() as conn:
                broken_status = await conn.fetchval(
                    "select status::text from knowledge.kb_versions where tag = $1",
                    f"{prefix}broken",
                )
            assert broken_status == "failed"
            assert await _version_status(pool, good_version_id) == "active"

            # ...and the previous version is still actually serving traffic.
            results = await search(
                pool,
                embedder,
                jurisdiction_id=jurisdiction_id,
                query="التزامات البائع",
                k=10,
                min_score=NO_SCORE_FLOOR,
            )
            assert len(results) == EXPECTED_CHUNKS

    asyncio.run(scenario())


def test_unverified_source_is_never_retrievable():
    """Exit criterion 5 / BR-24: chunks from an unverified source must not be
    returned, even when they are the active version's only content."""

    async def scenario():
        async with _sandbox() as (pool, jurisdiction_id, prefix, verifier_id):
            embedder = FakeEmbeddingProvider(settings.embedding_dimensions)
            document = await _seed_document(pool, jurisdiction_id, prefix, is_verified=False)

            kb_version_id = await rebuild_kb_version(
                pool,
                embedder,
                jurisdiction_id=jurisdiction_id,
                tag=f"{prefix}unverified",
                embedding_model="fake/deterministic",
                documents=[document],
            )
            assert await _version_status(pool, kb_version_id) == "active"

            results = await search(
                pool,
                embedder,
                jurisdiction_id=jurisdiction_id,
                query="التزامات البائع",
                k=10,
                min_score=NO_SCORE_FLOOR,
            )
            assert results == []

    asyncio.run(scenario())


def test_expired_chunks_are_never_retrievable():
    """Exit criterion 5: a law that has been repealed (effective_to in the
    past) must drop out of retrieval even from a verified source."""

    async def scenario():
        async with _sandbox() as (pool, jurisdiction_id, prefix, verifier_id):
            embedder = FakeEmbeddingProvider(settings.embedding_dimensions)
            _require_verifier(verifier_id)
            document = await _seed_document(
                pool,
                jurisdiction_id,
                prefix,
                verifier_id=verifier_id,
                effective_to=date(2021, 1, 1),
            )

            kb_version_id = await rebuild_kb_version(
                pool,
                embedder,
                jurisdiction_id=jurisdiction_id,
                tag=f"{prefix}expired",
                embedding_model="fake/deterministic",
                documents=[document],
            )
            assert await _version_status(pool, kb_version_id) == "active"

            results = await search(
                pool,
                embedder,
                jurisdiction_id=jurisdiction_id,
                query="التزامات البائع",
                k=10,
                min_score=NO_SCORE_FLOOR,
            )
            assert results == []

    asyncio.run(scenario())
