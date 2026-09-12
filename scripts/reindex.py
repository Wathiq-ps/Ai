"""Rebuild + activate a jurisdiction's kb_version from what's in
knowledge.documents. Same code path as the `reindex` job kind (UC-080) —
this is the ops entry point for running it without Laravel.

    uv run python scripts/reindex.py [JURISDICTION_CODE] [TAG]
"""

import asyncio
import sys
import time

from app.config import settings
from app.db import get_pool
from app.providers import get_embedding_provider
from app.reindex import reindex

CODE = sys.argv[1] if len(sys.argv) > 1 else "PS"
TAG = sys.argv[2] if len(sys.argv) > 2 else None


async def main():
    pool = await get_pool()
    jurisdiction_id = await pool.fetchval("select id from app.jurisdictions where code=$1", CODE)
    if jurisdiction_id is None:
        raise SystemExit(f"no jurisdiction {CODE!r} — is the Back-end migrated/seeded?")

    started = time.time()
    kb_version_id, documents = await reindex(
        pool, get_embedding_provider(), jurisdiction_id=jurisdiction_id,
        embedding_model=settings.embedding_model, tag=TAG,
    )
    print(f"kb_version {kb_version_id}  documents={documents}  {time.time() - started:.1f}s")
    for row in await pool.fetch("select tag, status, chunk_count from knowledge.kb_versions"):
        print(dict(row))
    await pool.close()


asyncio.run(main())
