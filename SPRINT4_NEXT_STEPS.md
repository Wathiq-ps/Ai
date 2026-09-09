# Sprint 4 — next steps (rewritten 2026-09-08)

Supersedes the 2026-09-07 version, which was stale on three points: the DB
blocker, whether the schema had ever been touched, and whether the SQL worked.

## Decision of record: West Bank law, assumed uniform

We build the corpus from **West Bank** statutes and proceed as if Palestinian
law is uniform across territories. The supervisor states the laws are the same,
and the West Bank sources are much cleaner regardless.

`LAW_CORPUS_RESEARCH.md` holds evidence pointing the other way (four of five
subject areas diverge; only مجلة الأحكام العدلية is definitely common). That
file is kept for the record, not to reopen the decision. The practical
consequence of the assumption being wrong is bounded: the general contract
layer carries ~11 of the 14 required clause groups, and the exposed clauses are
registration, competent court, and fees/tax.

**Therefore:** the existing `PS` / Palestine jurisdiction row stands. No
relabel, no second row, no further Back-end PR. Instead, record provenance per
source — `knowledge.sources.publisher` / `citation` / `source_url` naming the
actual West Bank instrument. Those columns have to be filled anyway, and they
keep the corpus partitionable later without re-collecting anything.

## What changed today

**The DB blocker is gone.** Railway rotated the Postgres TCP proxy; `.env` now
points at `autorack.proxy.rlwy.net:34688`. The old `altaria:33427` was dead.

**Schema verified live as `wathiq_ai`** — all four `knowledge.*` tables exist,
`chunks.embedding` is `vector(1536)`, `<=>` works under the restricted role,
and `app.contracts` / `app.users` are denied as designed.

**The embedder handles Arabic well.** Live check: query→relevant article 0.638,
query→unrelated 0.024, cross-lingual ar/en 0.491. `dimensions=1536` is honored
and renormalized. This was the biggest open risk before Sprint 5; it's closed.

**Seed re-embedded with the real model.** `gaza-seed-real-v1` is active,
`sprint4-seed-v1` superseded. Retrieval now puts the correct article first on
all three test queries (0.435 / 0.635 / 0.604).

**`app/knowledge.py`'s SQL is proven** — it had never executed before today.

**Back-end#6 merged**, seeding the jurisdiction via migration + seeder. Deploy
ran clean, row `id` unchanged.

## Sprint 4 status

| # | Task | State |
|---|---|---|
| 1 | Unblock DB access, verify schema | done |
| 2 | Move `vector` out of `public` into `extensions` | open, low priority |
| 3 | Integration test (rebuild → search) | done |
| 4 | Fail-closed test | done |
| 5 | BR-24 + effective-date tests | done |
| 6 | Seed a real corpus | **next** |
| 7 | Reindex trigger (UC-080) | open |
| 8 | Deploy AI service to Railway | open |

## Tomorrow

1. **Commit the pending work** — `tests/test_knowledge_integration.py`,
   `LAW_CORPUS_RESEARCH.md`, this file, `ISSUE_jurisdiction_seeder.md`. All
   still uncommitted.

2. **Start the corpus with مجلة الأحكام العدلية.** It is one document, it is
   the layer common to both territories, and it carries most of the 14 clause
   groups — the highest-value text to ingest first, ahead of any property
   statute. Then the West Bank property statutes from `mjr.ogb.gov.ps`:
   Law 49/1953 (sale/disposal), 62/1953 (landlord & tenant), 40/1952 (land and
   water settlement), 11/1954 (buildings and land tax).

3. **Build the document loader.** Nothing reads `knowledge.documents.raw_path`
   today — `ingest_document()` takes text in memory. Decide where raw files
   live and what `raw_path` holds. Loader notes from the research:
   - MJR returns **403 to non-browser user agents**; needs a realistic UA and
     respectful rate limiting.
   - Birzeit's Muqtafi is **HTTP-only** — every `*.birzeit.edu` host refuses
     TLS on 443. A fetcher that force-upgrades to HTTPS sees it as dead.
   - Land Authority sources are PDF-only and likely scans; not the first target.

4. **Reindex trigger (UC-080).** `POST` → 202 + job id, async, result to the
   Laravel callback; reuse the existing `/v1/jobs` shape rather than inventing
   a second job path. Note the endpoint **receives** verified source ids — it
   cannot create sources, because `sources_verified_complete` requires
   `verified_by` pointing at `app.users`, which `wathiq_ai` cannot read.
   Verification stays a human admin act in Laravel.

5. **Deploy the AI service to Railway** — new service in `Wathiq-Back`, private
   network, `postgres.railway.internal:5432` (not the public proxy). Set
   `AI_SERVICE_URL` / `AI_SERVICE_API_KEY` / `AI_WEBHOOK_SECRET` on both this
   service and Back-end. Blocks all of Sprint 7's Laravel wiring.

## Still open, not code

- **`wathiq_ai`'s password is the committed placeholder `ai`** and the DB is
  publicly reachable again through the new proxy. Rotate it.
- **OpenRouter's free tier logs every prompt and output** and is marked "trial
  use only". Fine for public law text, not for real client contracts. A paid
  embedding endpoint must be chosen before Sprint 7 — and switching models
  means re-embedding, so decide it while the golden set is being built.
- **No legal review yet.** The statute identification in
  `LAW_CORPUS_RESEARCH.md` is web-sourced. Worth asking the supervisor the one
  narrow question: does Law 49/1953 art. 18's repeal of the Ottoman 1913 law
  extend to Gaza? It either confirms his position with authority behind it or
  corrects the record cheaply.
- **`vector` resolves only because `public` leads the search_path.** Anything
  that narrows it (a `SECURITY DEFINER` function, a restricted role) breaks
  `vector(1536)` with a confusing "type does not exist".
