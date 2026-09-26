import asyncio
import contextlib
import hashlib
import uuid

from app.ingestion import detect_language, sha256_checksum
from app.knowledge import ingest_document


class _DocumentsTable:
    """Just enough of a pool to stand in for `knowledge.documents`."""

    def __init__(self):
        self.rows: list[dict] = []

    @contextlib.asynccontextmanager
    async def acquire(self):
        yield self

    async def fetchval(self, sql, source_id, checksum):
        return next((r["id"] for r in self.rows if (r["source_id"], r["checksum"]) == (source_id, checksum)), None)

    async def fetchrow(self, sql, source_id, title, language, checksum, raw_path):
        self.rows.append({"id": uuid.uuid4(), "source_id": source_id, "checksum": checksum})
        return self.rows[-1]


def test_reingesting_the_same_text_under_a_source_does_not_duplicate_it():
    """scripts/ingest_corpus.py is re-run whenever a law is added; every law
    already ingested must not get a second document (reindex would index it twice)."""
    table = _DocumentsTable()
    source_id, other_source = uuid.uuid4(), uuid.uuid4()

    async def scenario():
        first = await ingest_document(table, source_id=source_id, title="t", raw_text="المادة (1) نص")
        again = await ingest_document(table, source_id=source_id, title="t", raw_text="المادة (1) نص")
        edited = await ingest_document(table, source_id=source_id, title="t", raw_text="المادة (1) نص معدل")
        elsewhere = await ingest_document(table, source_id=other_source, title="t", raw_text="المادة (1) نص")
        return first, again, edited, elsewhere

    first, again, edited, elsewhere = asyncio.run(scenario())

    assert again == first
    assert len({first, edited, elsewhere}) == 3
    assert len(table.rows) == 3


def test_sha256_checksum_matches_hashlib():
    raw = b"some legal text"
    assert sha256_checksum(raw) == hashlib.sha256(raw).hexdigest()
    assert len(sha256_checksum(raw)) == 64


def test_detect_language_arabic():
    assert detect_language("هذا نص قانوني باللغة العربية يخص عقد البيع") == "ar"


def test_detect_language_english():
    assert detect_language("This is a legal text regarding a sale contract") == "en"


def test_detect_language_empty_defaults_to_en():
    assert detect_language("123 456") == "en"
