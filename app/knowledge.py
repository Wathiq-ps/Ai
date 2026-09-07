"""Sprint 4 (1B) — ingestion, versioned rebuild, retrieval against
`knowledge.*`. See WATHIQ_AI_SPRINT_PLAN.md."""

import json
import uuid
from dataclasses import dataclass
from datetime import date

import asyncpg

from app.chunking import Chunk, chunk_document
from app.ingestion import detect_language, sha256_checksum
from app.providers.base import EmbeddingProvider


@dataclass
class DocumentForIndex:
    """One law document's worth of chunking input for a kb_version rebuild."""

    document_id: uuid.UUID
    jurisdiction_id: uuid.UUID
    law_type: str
    text: str
    effective_from: date
    effective_to: date | None = None


@dataclass
class SearchResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float
    law_type: str
    article: str | None
    effective_from: date
    effective_to: date | None


async def ingest_document(
    pool: asyncpg.Pool, *, source_id: uuid.UUID, title: str, raw_text: str, language: str | None = None
) -> uuid.UUID:
    """Register one document under an existing `knowledge.sources` row:
    checksum + ar/en detect, insert into `knowledge.documents`."""
    checksum = sha256_checksum(raw_text.encode("utf-8"))
    lang = language or detect_language(raw_text)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into knowledge.documents (source_id, title, language, checksum)
            values ($1, $2, $3::app.locale, $4)
            returning id
            """,
            source_id,
            title,
            lang,
            checksum,
        )
    return row["id"]


class KbVersionBuildFailed(Exception):
    pass


async def rebuild_kb_version(
    pool: asyncpg.Pool,
    embedder: EmbeddingProvider,
    *,
    jurisdiction_id: uuid.UUID,
    tag: str,
    embedding_model: str,
    documents: list[DocumentForIndex],
    notes: str | None = None,
) -> uuid.UUID:
    """Versioned rebuild: `building` -> chunk+embed+upsert -> verify counts ->
    atomic flip to `active` (old active -> `superseded`). Fails closed: on a
    count mismatch the new version is left `failed` and never activated —
    the previous `active` version keeps serving (Sprint 4 exit criterion)."""
    chunked: list[tuple[DocumentForIndex, list[Chunk]]] = [
        (doc, chunk_document(doc.text)) for doc in documents
    ]
    expected_count = sum(len(chunks) for _, chunks in chunked)

    async with pool.acquire() as conn:
        kb_version_id = await conn.fetchval(
            """
            insert into knowledge.kb_versions
                (tag, jurisdiction_id, embedding_model, embedding_dimensions, status, notes)
            values ($1, $2, $3, $4, 'building', $5)
            returning id
            """,
            tag,
            jurisdiction_id,
            embedding_model,
            embedder.dimensions,
            notes,
        )

        try:
            for doc, chunks in chunked:
                if not chunks:
                    continue
                vectors = await embedder.embed([c.content for c in chunks])
                await conn.executemany(
                    """
                    insert into knowledge.chunks
                        (kb_version_id, document_id, jurisdiction_id, law_type, ordinal,
                         content, token_count, embedding, effective_from, effective_to, metadata)
                    values ($1, $2, $3, $4::app.law_type, $5, $6, $7, $8, $9, $10, $11::jsonb)
                    """,
                    [
                        (
                            kb_version_id,
                            doc.document_id,
                            doc.jurisdiction_id,
                            doc.law_type,
                            chunk.ordinal,
                            chunk.content,
                            chunk.token_count,
                            vector,
                            doc.effective_from,
                            doc.effective_to,
                            _to_jsonb(chunk.metadata),
                        )
                        for chunk, vector in zip(chunks, vectors)
                    ],
                )

            actual_count = await conn.fetchval(
                "select count(*) from knowledge.chunks where kb_version_id = $1", kb_version_id
            )
            if actual_count != expected_count:
                raise KbVersionBuildFailed(
                    f"kb_version {kb_version_id}: expected {expected_count} chunks, wrote {actual_count}"
                )

            async with conn.transaction():
                await conn.execute(
                    """
                    update knowledge.kb_versions
                    set status = 'superseded'
                    where jurisdiction_id = $1 and status = 'active'
                    """,
                    jurisdiction_id,
                )
                await conn.execute(
                    """
                    update knowledge.kb_versions
                    set status = 'active', chunk_count = $2, built_at = now(), activated_at = now()
                    where id = $1
                    """,
                    kb_version_id,
                    actual_count,
                )
        except Exception:
            await conn.execute(
                "update knowledge.kb_versions set status = 'failed' where id = $1", kb_version_id
            )
            raise

    return kb_version_id


def _to_jsonb(metadata: dict) -> str:
    return json.dumps(metadata)


async def search(
    pool: asyncpg.Pool,
    embedder: EmbeddingProvider,
    *,
    jurisdiction_id: uuid.UUID,
    query: str,
    law_type: str | None = None,
    k: int = 10,
    min_score: float = 0.0,
) -> list[SearchResult]:
    """search(jurisdiction_id, law_type?, query, k, min_score) — only the
    `active` kb_version, only `is_verified` sources (BR-24), only chunks
    currently in effect."""
    [query_vector] = await embedder.embed([query])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select * from (
                select
                    c.id as chunk_id,
                    c.document_id,
                    c.content,
                    c.law_type::text as law_type,
                    c.metadata ->> 'article' as article,
                    c.effective_from,
                    c.effective_to,
                    1 - (c.embedding <=> $1) as score
                from knowledge.chunks c
                join knowledge.kb_versions v on v.id = c.kb_version_id
                join knowledge.documents d on d.id = c.document_id
                join knowledge.sources s on s.id = d.source_id
                where v.jurisdiction_id = $2
                  and v.status = 'active'
                  and s.is_verified
                  and c.effective_from <= current_date
                  and (c.effective_to is null or c.effective_to > current_date)
                  and ($3::app.law_type is null or c.law_type = $3::app.law_type)
            ) scored
            where score >= $5
            order by score desc
            limit $4
            """,
            query_vector,
            jurisdiction_id,
            law_type,
            k,
            min_score,
        )

    return [
        SearchResult(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            content=row["content"],
            score=row["score"],
            law_type=row["law_type"],
            article=row["article"],
            effective_from=row["effective_from"],
            effective_to=row["effective_to"],
        )
        for row in rows
    ]
