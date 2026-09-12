"""UC-080 — reindex: turn what's already in `knowledge.documents` into a new
active `kb_version`. Sprint 4 item 7.

Reuses `rebuild_kb_version()` (chunk -> embed -> verify counts -> atomic flip);
this module is only the "what goes in the index" half: every document of one
jurisdiction, text re-read from `raw_path` so the index always reflects the
file on disk rather than whatever was in memory at ingest time.

Note the endpoint cannot verify sources — `sources_verified_complete` needs a
`verified_by` in `app.users`, which the `wathiq_ai` role cannot read.
Verification stays a human admin act in Laravel; unverified sources are
indexed but `search()` won't serve them (BR-24).
"""

import uuid
from datetime import datetime, timezone

import asyncpg

from app.document_loader import UnsupportedDocumentFormat, load_corpus_file
from app.knowledge import DocumentForIndex, rebuild_kb_version
from app.providers.base import EmbeddingProvider


class ReindexFailed(Exception):
    pass


async def collect_documents(pool: asyncpg.Pool, *, jurisdiction_id: uuid.UUID) -> list[DocumentForIndex]:
    """Every document of this jurisdiction that has a readable raw file.
    Documents whose format has no loader yet (scanned PDFs — see
    SPRINT4_NEXT_STEPS.md) are skipped, not fatal: the rest still index."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select d.id, d.raw_path, s.law_type::text as law_type, s.effective_from, s.effective_to
            from knowledge.documents d
            join knowledge.sources s on s.id = d.source_id
            where s.jurisdiction_id = $1
            order by d.created_at
            """,
            jurisdiction_id,
        )

    documents: list[DocumentForIndex] = []
    for row in rows:
        if not row["raw_path"]:
            continue
        try:
            text, _ = load_corpus_file(row["raw_path"].removeprefix("corpus/"))
        except (UnsupportedDocumentFormat, FileNotFoundError):
            continue
        documents.append(
            DocumentForIndex(
                document_id=row["id"],
                jurisdiction_id=jurisdiction_id,
                law_type=row["law_type"],
                text=text,
                effective_from=row["effective_from"],
                effective_to=row["effective_to"],
            )
        )
    return documents


async def reindex(
    pool: asyncpg.Pool,
    embedder: EmbeddingProvider,
    *,
    jurisdiction_id: uuid.UUID,
    embedding_model: str,
    tag: str | None = None,
    notes: str | None = None,
) -> tuple[uuid.UUID, int]:
    """Build and activate a fresh kb_version. Returns (kb_version_id, documents)."""
    documents = await collect_documents(pool, jurisdiction_id=jurisdiction_id)
    if not documents:
        raise ReindexFailed("no loadable documents for this jurisdiction")

    kb_version_id = await rebuild_kb_version(
        pool,
        embedder,
        jurisdiction_id=jurisdiction_id,
        tag=tag or f"reindex-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}",
        embedding_model=embedding_model,
        documents=documents,
        notes=notes,
    )
    return kb_version_id, len(documents)
