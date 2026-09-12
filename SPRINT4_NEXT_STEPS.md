# Sprint 4 — next steps (rewritten 2026-09-08)

Supersedes the 2026-09-07 version, which was stale on three points: the DB
blocker, whether the schema had ever been touched, and whether the SQL worked.

## 2026-09-12 update: Sprint 6 agent built, corpus indexing hit the free-tier cap

Built today (all committed, 59 tests green):

- **`analyze_contract` (Sprint 6 / 1D)** — `app/analyze_contract.py`, same
  shape as the drafting agent: retrieve per clause topic, one LLM call with a
  bounded JSON-repair loop, citations hydrated from our own retrieval so a
  finding cannot cite law we never read (BR-25). Risk score is computed here,
  not asked of the model: severity-weighted sum capped at 100, versioned
  `risk-v1` (closes open decision #5's determinism half).
- **`reindex` job kind (UC-080)** — `app/reindex.py` + `scripts/reindex.py`.
  Rebuilds a jurisdiction's kb_version from the documents already in
  `knowledge.documents`, re-reading each `raw_path`. Scanned PDFs with no
  loader are skipped, not fatal.
- **60s job budget (NFR-1.1)** — over budget now ends in a signed `timed_out`
  callback. Reindex is exempt (a rebuild is minutes of embedding calls).
- **Deploy artifact** — `Dockerfile` (uv image, `$PORT`, single worker).
  Verified locally: builds at 313MB, container answers `/health`.
- **Embedder actually works now.** Three real bugs, all live-verified fixed:
  the model id `nvidia/llama-nemotron-embed-vl-1b-v2:free` no longer resolves
  (now `nvidia/nemotron-3-embed-1b:free`); nothing passed `native_dimensions`,
  so every request asked for 1536 and got a 400; and `math` was used without
  being imported. Live: 1536-d unit vectors, ar/en cosine 0.546.

- **RAG eval harness (Sprint 5 / 1B′)** — `app/retrieval_eval.py`,
  `eval/golden_set.jsonl` (15 Arabic question → article pairs from the three
  West Bank statutes), `scripts/run_eval.py`. Scores by *article label*, not
  chunk id, so the golden set survives re-chunking; F2 because a missed
  article costs more than an extra one. Verified offline that every expected
  label is one the chunker actually produces. The live run waits on the two
  blockers below.
- **The rebuild write path is now proven against the real DB** — it had never
  completed before today (both live attempts died on env/quota before the
  insert). With deterministic fake vectors: 4 documents → 1714 chunks →
  count verified → atomic flip to `active`, 14.1s, rows deleted after. Same
  run confirms BR-24 live: `search()` returns 0 hits while the sources are
  unverified, even with a full index in place.

### Blocked, needs you

1. **OpenRouter free tier is out of quota for the day** — 50 requests/day, and
   a full-corpus rebuild costs 7 at the new batch size of 256 (it cost 27
   before; two failed attempts burned the day). Nothing is indexed:
   `knowledge.chunks` is empty and there is no `kb_version` row, so retrieval
   returns nothing and both agents correctly fail closed. Either wait for the
   daily reset and run `uv run python scripts/reindex.py PS real-corpus-v1`,
   or add credits — this is the same paid-endpoint decision already flagged
   below under "Still open, not code", now forced.
2. **The four seeded sources are `is_verified = false`.** Only Laravel can
   verify them (`sources_verified_complete` needs a `verified_by` in
   `app.users`, which `wathiq_ai` cannot read). Until an admin verifies them,
   `search()` serves nothing even with an index built (BR-24).
3. **Railway deploy needs your credentials** — no Railway CLI on this machine
   and the MCP server is unauthenticated. The Dockerfile is ready; the service
   still has to be created in `Wathiq-Back` on the private network, with
   `AI_SERVICE_URL` / `AI_SERVICE_API_KEY` / `AI_WEBHOOK_SECRET` set on both
   sides. This is what blocks Sprint 7's Laravel wiring.

Not touched: the RAG eval harness / golden set (Sprint 5's first half), PDF
OCR for the two scanned statutes, `answer_query`/`summarize`.

## 2026-09-09 update: corpus hunt happened, hit an OCR wall

Since this doc was written: `generate_contract` (Sprint 5, the drafting node)
is built, wired into `/v1/jobs`, and passed a live end-to-end smoke test
against the real DB/embedder/DeepSeek — see git log, not repeated here. This
update is scoped to what changed on **this doc's own open items** (2 and 3
below, plus one item under "Still open, not code").

**Item 3 (document loader) is done** — `app/document_loader.py` reads local
corpus files and wires `raw_path` through `ingest_document()`. Only
`.txt`/`.md` supported; PDF/DOCX deferred until real files existed to test
against. They now do (see next point), and both are scans — so that
deferral is now blocking, not hypothetical.

**Item 2 (start the corpus) hit a real wall: two of the four target statutes
don't check out, and everything obtainable so far is a scan.**

- **مجلة الأحكام العدلية** — found and downloaded, `corpus/majalla-1293h.pdf`
  (292pp), via `dftp.gov.ps` (the gazette authority, not MJR/Muqtafi).
  Status ساري المفعول.
- **"Law 49/1953" (sale/disposal) — does not exist under that citation.**
  Exhaustively checked MJR (title, full-text, category, by-number) and
  dftp.gov.ps (by-number across every era, by-title in the Jordanian era):
  zero hits. What's actually in force is the **Ottoman** law `قانون التصرف
  بالأموال غير المنقولة` (1331هـ) — downloaded,
  `corpus/immovable-property-disposal-1331h.pdf` (6pp). Full detail and the
  corrected citation table are in `LAW_CORPUS_RESEARCH.md`'s 2026-09-09
  update section — read that before touching this statute again.
- **62/1953 (landlord/tenant) and 11/1954 (buildings/land tax) — located at
  MJR**, not yet downloaded/OCR'd: `https://mjr.ogb.gov.ps/MergedLegislations/ViewText/119`
  (62/1953), and search MJR's consolidated index for
  `قانون ضريبة الأبنية والأراضي ... رقم (11) لسنة 1954` (11/1954).
- **40/1952 (land & water settlement) — not found yet.** Title-text search on
  MJR only surfaced fee *regulations* referencing it (`نظام` type, different
  numbers), not the law itself. Same treatment as 49/1953 was needed but
  wasn't finished — try `dftp.gov.ps`'s era filter next, not more MJR title
  guessing.
- **Both downloaded PDFs are scans, no text layer** (confirmed via
  `pdftotext`/`pdfinfo` — Mejelle via old Acrobat import, the Ottoman law via
  PaperScan scanner software). `document_loader.py` can't ingest either as-is.
  Next call: try a cheap tesseract-Arabic pass before committing to
  self-hosted QARI-OCR (already flagged as deferred infra work below and in
  `WATHIQ_AI_SPRINT_PLAN.md`'s Phase 0 section).
- **MJR's 403 is a real Cloudflare JS challenge, not a UA check** — a real
  browser passes with zero friction, no login, no bypass needed. Muqtafi
  remains a dead end for scripted access (session-gated ASP.NET postback
  form); use it manually or not at all.

This makes item 6 in the Sprint 4 status table below still accurately
"next" — corpus seeding isn't done, it's now blocked on OCR rather than on
finding the documents.

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
  `LAW_CORPUS_RESEARCH.md` is web-sourced. The original narrow question here
  ("does Law 49/1953 art. 18's repeal of the Ottoman 1913 law extend to
  Gaza?") is moot — 2026-09-09 corpus hunting found no verifiable Law
  49/1953 at all (see that file's update section). Revised question for the
  supervisor: is the Ottoman `قانون التصرف بالأموال غير المنقولة` (1331هـ)
  actually the operative sale/disposal statute in the West Bank too, or does
  a real (differently-numbered or differently-titled) Jordanian statute
  supersede it there? Answering this cheaply prevents building on the wrong
  citation.
- **`vector` resolves only because `public` leads the search_path.** Anything
  that narrows it (a `SECURITY DEFINER` function, a restricted role) breaks
  `vector(1536)` with a confusing "type does not exist".
