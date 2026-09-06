# Wathiq AI Legal Engine — Sprint Plan & Task Breakdown

> Derived from `AI_IMPLEMENTATION_PLAN.md` (verified accurate against migrations + SRS on 2026-08-18).
> This file schedules that plan into sprints. It does not re-derive scope — see the source plan for the "why".

## Schedule anchor

- Sprint cadence: **2 weeks**, Monday start.
- Sprint 1 nominally started **2026-07-27** (1 month before this plan was written, 2026-08-22).
- Reality check: `AI/` is still empty, `AI_IMPLEMENTATION_PLAN.md` is untracked, and every Phase 0 decision (§6 of the plan) is still open. **Zero of Sprint 1–2 shipped.** You are not "behind" on execution — you're behind on *starting*. Sprint 3 below is rewritten as a **Catch-Up Sprint** that absorbs Sprint 1+2 scope, starting today.

| Sprint | Dates | Status |
|---|---|---|
| Sprint 1 | 2026-07-27 – 2026-08-07 | ⚠️ Missed — scope folded into Catch-Up |
| Sprint 2 | 2026-08-10 – 2026-08-21 | ⚠️ Missed — scope folded into Catch-Up |
| **Catch-Up (Sprint 3)** | **2026-08-24 – 2026-09-04** | ▶ Starts now |
| Sprint 4 | 2026-09-07 – 2026-09-18 | Planned |
| Sprint 5 | 2026-09-21 – 2026-10-02 | Planned |
| Sprint 6 | 2026-10-05 – 2026-10-16 | Planned |
| Sprint 7 | 2026-10-19 – 2026-10-30 | Planned |
| Sprint 8 | 2026-11-02 – 2026-11-13 | Planned |

---

## Catch-Up Sprint (2026-08-24 – 2026-09-04) — Phase 0 + 1A

Compressed: decisions block everything else, so they go first and fast. Skeleton runs in parallel once decided.

**Phase 0 — Decisions & foundations**
- [x] **Embedding model — Qwen3-Embedding-8B** (Alibaba/Qwen, open-weight) via **DeepInfra**'s OpenAI-compatible API. Native output is 4096-d, truncated to **1536** via the `dimensions` request param to match `knowledge.chunks.embedding vector(1536)` already migrated — no schema edit, no re-embed risk. Picked over OpenAI's text-embedding-3 line after comparing DeepInfra's whole catalog: best multilingual score of the viable options, same-or-lower price, and 32k context (vs OpenAI's 8k) so a full law article chunks without truncating. Arabic quality is still unverified in production — Sprint 5's golden-set harness is the real gate; revisit here + `000601_*` if it scores badly.
- [x] **LLM provider — DeepSeek-V4-Pro** (DeepSeek AI) via **OpenRouter** (`deepseek/deepseek-v4-pro`) — cheaper there than DeepSeek's own direct API, plus failover across ~17 backend providers. Picked over Azure OpenAI and explicitly over Claude (ruled out on cost): cheapest model found that's actually reasoning-tuned (needed for `analyze_contract`'s multi-step finding logic), 1M context fits a full contract + every retrieved citation in one call. SRS's "Microsoft Copilot (replaceable)" — this is the swap; `app/providers/base.py`'s `LLMProvider` interface keeps it swappable again. Trade-off: this leaves Azure's data-residency story for the *database* only (§ below) — no residency requirement has been raised against DeepSeek/OpenRouter specifically, revisit if one is.
- [x] Ratify Python/FastAPI + LangGraph, pgvector (no HNSW at launch) — already implied by schema/SRS, this line just confirms it in writing. Package manager: `uv`.
- [x] AI service's restricted Postgres role (`knowledge.*` only, no `app.contracts`) — **already existed**, `2026_08_04_990000_grant_wathiq_privileges.php` (`wathiq_ai` role: full `knowledge.*`, narrow `app.jurisdictions`/`app.countries`/`app.ai_jobs` slice, explicit revoke on `app.contracts` etc.). Nothing built here; `app.assert_privilege_invariants()` already asserts the boundary in CI.
- [x] OpenAPI wire contract: `generate_contract`/`analyze_contract` request/response + webhook callback shape + HMAC scheme — `AI/openapi.yaml`. HMAC: outbound callback signed `HMAC-SHA256(webhook_secret, timestamp + "." + raw_body)`, header `X-Wathiq-Signature: t=<ts>,v1=<hex digest>`, Laravel rejects if >5 min old (replay defense via `ops.webhook_deliveries` unique index). Inbound uses static `X-API-Key` — fine for one internal caller, revisit if a second caller needs direct access.
- [x] Shared `.env` config — root `.env.example` + `AI/.env.example`, both sides read the same `AI_SERVICE_URL`/`AI_WEBHOOK_SECRET`/`AI_SERVICE_API_KEY` — kept in sync manually until there's a shared secrets store.
- **Exit:** all six items resolved 2026-08-23, embedding dimension final (1536, truncated from Qwen3's native 4096).

**Deferred — OCR for scanned documents** (KYC IDs, deeds, legacy paper contracts; Phase-3-and-later scope per `AI_IMPLEMENTATION_PLAN.md`, not blocking Phase 1): GLM-OCR is cheap/managed but **confirmed no Arabic support** (official 8-language list excludes it, fails on real Arabic input). QARI-OCR (Qwen2-VL/Qwen3-VL fine-tune) is purpose-built for Arabic and open-weight but has **no managed hosting anywhere** — self-host only. User wants the accurate option over the cheap one here, so QARI-OCR self-hosted is the leading candidate. Hosting plan for when it's built: **Modal** — both QARI-OCR and Qwen3-Embedding-8B fit Modal's cheapest GPU (A10G, ~$1.10/hr); the $30/month free credit (~26 GPU-hours) covers dev/testing, not always-on production. Bake weights into the image/a Volume, don't re-download on every cold start.

**1A — AI service skeleton**
- [x] Scaffold `AI/` (FastAPI + uv/poetry + LangGraph) — LangGraph dep deferred to 1C when agents are actually built, see `AI/README.md`
- [x] `LLMProvider` + `EmbeddingProvider` abstractions, one real adapter + one fake/deterministic adapter for tests — `app/providers/{base,openai_compatible,fake}.py`
- [x] `/health`, `/v1/jobs`, callback route — `/health` + `/v1/jobs` live; `/v1/jobs/{id}/callback` is Laravel-side (1E.4), documented in `openapi.yaml`
- [x] Structured logging, trace ids, usage metrics (tokens, latency) — `app/logging_conf.py`, timing middleware in `app/main.py`; per-call token/latency usage wiring lands with the real agents (1C/1D)
- [x] API key check inbound, HMAC signing outbound — `app/security.py`
- **Exit:** service boots, `/health` → 200, smoke job round-trips. Verified 2026-08-23 (`uv run pytest` 3 passed; live `curl /health` → `{"status":"ok"}`)

---

## Sprint 4 (2026-09-07 – 2026-09-18) — 1B Ingestion & retrieval

- [ ] Document intake: load raw text from `knowledge.sources/documents`, SHA-256, `ar`/`en` detection
- [ ] Arabic-aware chunking (sentence/paragraph + article-number anchors), chunk metadata
- [ ] Per-chunk embedding respecting `kb_versions.embedding_dimensions`
- [ ] Versioned rebuild: new `kb_versions` row `building` → upsert → verify counts → atomic flip to `active` → old one `superseded`
- [ ] Retrieval: `search(jurisdiction_id, law_type?, query, k, min_score)`, filtered by `is_verified` (BR-24) + effective dates
- [ ] Reindex trigger on KB update (UC-080)
- **Exit:** seed small Palestinian-law corpus; reindex end-to-end; retrieval returns cited, verified chunks; only active version served.

## Sprint 5 (2026-09-21 – 2026-10-02) — 1B′ RAG eval harness + 1C generation agent

- [ ] Port `autoretrieval`'s scoring math (Recall/Precision/IoU/F-beta) — language-agnostic, drops in as-is
- [ ] Port `generate_dataset.py` pattern → Arabic legal golden-set (question → article reference)
- [ ] Replace `SentenceChunker` with the Arabic chunker from Sprint 4
- [ ] Point `get_retrieval_pipeline()` at pgvector `knowledge.chunks`, not Chroma — eval the real retriever
- [ ] Run eval, tune embedding model/`k`/chunk size against the golden set (closes open decision #1 and #4)
- [ ] `generate_contract` LangGraph node: retrieve → select jurisdiction law → draft (14 required clause groups, FR-6.2) → ground with citations
- [ ] Fail-closed: no verified sources / KB unreachable → job `failed`, no draft (BR-28)
- **Exit:** golden-set regression gate in place; given a verified request, AI returns a structurally complete cited draft; disabling retrieval proves no draft is produced.

## Sprint 6 (2026-10-05 – 2026-10-16) — 1D analysis agent + 1E part 1

- [ ] `analyze_contract` graph: completeness, legal-conflict, ambiguity, suggestion, risk findings — every finding non-empty `citations[]` (BR-25)
- [ ] Legal Risk Score: deterministic 0–100, severity-weighted, versioned rubric (open decision #5)
- [ ] Analysis report: summary_ar/en, reviewed/proposed/violating clauses, risk, confidence, citations, model+KB version
- [ ] Eloquent models: `AiJob`, `ContractAnalysis`, `AnalysisFinding`, `ContractClause`, `ContractVersion`, Knowledge models
- [ ] `AiJobService::enqueue()` — `ai_jobs` + `ops.outbox` row in one transaction, `input_hash`
- **Exit:** flawed draft → correct findings + band + confidence, empty-citation findings impossible; enqueue is transactional.

## Sprint 7 (2026-10-19 – 2026-10-30) — 1E part 2

- [ ] Outbox relay worker: claim `FOR UPDATE SKIP LOCKED`, POST to AI service, mark `dispatched`, retry+backoff, timeout → `timed_out` (60s budget, NFR-1.1)
- [ ] Inbound webhook controller: verify HMAC + replay-proof, write results, drive state transitions (draft → under_ai_review → pending_lawyer_review), failure → back to draft + notify
- [ ] Lawyer review endpoints: list/get, accept/reject findings, edit clauses (new immutable version), approve (BR-29 gate)
- [ ] Export: PDF (ar/en, RTL), sealed PDF, share link
- [ ] KB admin endpoints: CRUD sources/documents + verification workflow, trigger reindex
- [ ] Provenance + audit: populate `ai_jobs.provider/model_id/...`, `audit_logs` on every transition
- **Exit:** end-to-end happy path runs async with correct transitions; replayed webhook rejected; killed AI service fails closed.

## Sprint 8 (2026-11-02 – 2026-11-13) — 1F clients + hardening → Phase 1 done

- [ ] Mobile: contract list/detail, AI draft view, analysis view w/ accept-reject, lawyer review, signature, export
- [ ] Front: admin KB console (sources, verification, reindex status), lawyer review dashboard
- [ ] NFR-12.2 disclaimer + confidence shown everywhere AI output appears
- [ ] Harden: retries, replay defense, timeouts, observability, audit — measure against NFR-1.1 (60s) / NFR-1.4 (1000 concurrent)
- **Exit (Phase 1 done):** full AI contract lifecycle on Palestinian law, KB-grounded, lawyer-gated, provenance + audit — SRS Phase-1 AI scope met.

---

## Notes
- Growth (Phase 2, no new AI) and Maturity (Phase 3: usage reports, property comparison, translation, law-version UI, Q&A/summarize) are intentionally not scheduled — pull from `AI_IMPLEMENTATION_PLAN.md` §4 Phase 2/3 once Phase 1 ships.
- If Catch-Up Sprint decisions slip past 2026-09-04, everything downstream shifts 1:1 — the dependency chain (§5 of the plan) is strict: retrieval blocks generation blocks analysis blocks Laravel wiring blocks clients.
