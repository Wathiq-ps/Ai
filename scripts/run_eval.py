"""Run the golden-set eval against the live active kb_version.

    uv run python scripts/run_eval.py [K]

Needs DATABASE_URL + OPENROUTER_API_KEY and an active, verified KB — with
unverified sources search() returns nothing and every score is 0 by design.
"""

import asyncio
import sys

from app.db import get_pool
from app.knowledge import search
from app.providers import get_embedding_provider
from app.retrieval_eval import load_golden_set, macro_average, score_query

K = int(sys.argv[1]) if len(sys.argv) > 1 else 5


async def main():
    pool = await get_pool()
    embedder = get_embedding_provider()
    jurisdiction_id = await pool.fetchval("select id from app.jurisdictions where code='PS'")
    queries = load_golden_set()

    scores = []
    for query in queries:
        results = await search(
            pool, embedder, jurisdiction_id=jurisdiction_id, query=query.question,
            law_type=query.law_type, k=K,
        )
        score = score_query(query, [r.article for r in results])
        scores.append(score)
        print(f"{score.id:34s} recall={score.recall:.2f} prec={score.precision:.2f} "
              f"f2={score.f_beta:.2f}  expected={score.expected} got={score.retrieved}")

    print("\nmacro:", macro_average(scores), f"(k={K}, n={len(scores)})")
    await pool.close()


asyncio.run(main())
