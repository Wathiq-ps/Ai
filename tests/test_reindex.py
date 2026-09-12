import asyncio
import uuid
from datetime import date

import pytest

import app.reindex as rx
from app.reindex import ReindexFailed, reindex

JURISDICTION_ID = uuid.uuid4()


def test_reindex_fails_closed_when_nothing_is_loadable(monkeypatch):
    async def _none(*args, **kwargs):
        return []

    monkeypatch.setattr(rx, "collect_documents", _none)

    with pytest.raises(ReindexFailed):
        asyncio.run(reindex(None, None, jurisdiction_id=JURISDICTION_ID, embedding_model="m"))


def test_reindex_activates_a_version_and_reports_document_count(monkeypatch):
    kb_version_id = uuid.uuid4()
    docs = [
        rx.DocumentForIndex(
            document_id=uuid.uuid4(), jurisdiction_id=JURISDICTION_ID, law_type="rent",
            text="نص", effective_from=date(1953, 1, 1),
        )
    ]
    seen = {}

    async def _collect(*args, **kwargs):
        return docs

    async def _rebuild(pool, embedder, **kwargs):
        seen.update(kwargs)
        return kb_version_id

    monkeypatch.setattr(rx, "collect_documents", _collect)
    monkeypatch.setattr(rx, "rebuild_kb_version", _rebuild)

    result = asyncio.run(
        reindex(None, None, jurisdiction_id=JURISDICTION_ID, embedding_model="m", notes="n")
    )

    assert result == (kb_version_id, 1)
    assert seen["documents"] == docs
    assert seen["tag"].startswith("reindex-")  # generated, not required from the caller
