# Wathiq — AI System Implementation Plan

> Derived from `wathiq_SRS_V05.pdf` (v5.0, July 2026), the repository state as of this analysis,
> and the database schema already migrated under `Back-end/wathiq/database/migrations/`.
> This document is a build plan, not a requirements document — the SRS is authoritative for scope.

---

## 1. What this repo already contains (current state)

| Area | Status |
|---|---|
| `AI/` | **Empty** (`.gitkeep` only). The AI Legal Engine microservice does not exist yet. |
| `Front/` | **Empty** (`.gitkeep` only). Web dashboards not started. |
| `Mobile/` | Flutter skeleton only (auth feature scaffolded). No contract/AI screens. |
| `Back-end/wathiq/` | Fresh Laravel app, but with a **complete, unusually well-designed PostgreSQL schema** already migrated — including the entire AI boundary. No application PHP logic yet (only default `Controller.php` / `User.php`, `routes/web.php` is the Laravel welcome page). |

### The AI data layer that already exists (read these before writing any code)

- `knowledge.kb_versions` — versioned knowledge bases, one `active` per jurisdiction, records `embedding_model` + `embedding_dimensions` (currently **1536**, an open item).
- `knowledge.sources` — laws/regulations/templates, with `is_verified`, `verified_by`, `effective_from/to`.
- `knowledge.documents` — ingested documents, SHA-256 `checksum`, language, `article_ref`.
- `knowledge.chunks` — chunked text with `embedding vector(1536)`, `law_type`, effective dates, `metadata jsonb`. (pgvector, **no HNSW index at launch** — deliberately, see migration comment.)
- `app.ai_jobs` — the async boundary. `kind` ∈ `generate_contract | analyze_contract | answer_query | summarize`; status lifecycle `queued → dispatched → running → succeeded | failed | cancelled | timed_out`; **provenance columns** (`provider, model_id, model_version, prompt_version, kb_version_id`) enforced by a check constraint on success (NFR-12.3).
- `app.contract_analyses` — one per contract version; integer `risk_score` (0–100) with a generated `risk_band` column.
- `app.analysis_findings` — `kind` ∈ `missing_clause | legal_conflict | ambiguity | suggestion | risk`; `severity`; `resolution` (`open/accepted/rejected/superseded`); **`citations jsonb`** for grounding (BR-25 / NFR-12.3).
- `app.contract_clauses` — clause-level breakdown, append-only (`reject_any_change` trigger), `is_ai_generated` flag.
- `app.contract_versions` — append-only, `content_hash` (SHA-256), `author_type` ∈ `ai | lawyer | owner | admin | system`, links `ai_job_id`.
- `app.contract_status_transitions_allowed` + `enforce_contract_transition()` trigger — the state machine enforced in the DB.
- `ops.outbox` + `ops.webhook_deliveries` — transactional outbox and **signed webhook** delivery/replay-defense for the AI service (and future gateways).

**Implication:** the persistence and integrity story for AI is already 80% done. The missing pieces are (a) the AI microservice itself, (b) the Laravel application logic (controllers/services/jobs/relay), and (c) the clients (Mobile/Front screens).

---

## 2. AI features identified from the SRS

### 2.1 MVP (Phase 1) — the core AI Legal Engine

| # | Feature | SRS traceability | Builds on |
|---|---|---|---|
| A1 | AI contract **drafting** grounded in local law (RAG) | FR-6.2, FR-6.4, UC-047, BR-23/BR-25 | `generate_contract` job |
| A2 | **Jurisdiction-aware law selection** (country/region → applicable law) | FR-6.3 | `jurisdictions`, `knowledge.kb_versions` |
| A3 | **RAG retrieval** (embed query → search vector store → return cited sources) | FR-6.4, UC-057 | `knowledge.chunks`, pgvector |
| A4 | **Contract analysis** (completeness, conflicts, missing/ambiguous clauses, risk, law compliance) | FR-6.5, UC-048 | `analyze_contract` job |
| A5 | **Legal Risk Score** 0–100 with bands + confidence | FR-6.6, UC-049, BR-27 | `contract_analyses` |
| A6 | **Missing-clause detection** + suggested additions | FR-6.7, UC-050 | `analysis_findings` |
| A7 | **Legal-conflict detection** (clause vs. legislation, with article citation) | FR-6.8 | `analysis_findings.citations` |
| A8 | **Amendment suggestions** with impact explanation | FR-6.9 | `analysis_findings.suggested_text` |
| A9 | **Analysis report** (summary, status, reviewed/proposed/violating clauses, risk, confidence, citations, model version, date) | FR-6.10, UC-048 | `contract_analyses.report_path` |
| A10 | **Lawyer review** — read, edit clauses, annotate, accept/reject AI suggestions, request changes | FR-6.11, UC-028/029/070 | findings `resolution` |
| A11 | **Approval gate** — only a licensed lawyer may approve; AI output never final | FR-6.12, BR-25/BR-26/BR-29 | state machine |
| A12 | **Versioning + audit trail** | FR-6.13/6.14, BR-22, UC-009 | `contract_versions`, `audit_logs` |
| A13 | **Contract export** (PDF, print, signed copy, secure share link) | FR-6.15, UC-059 | `contract_seals`, final PDF |
| A14 | **Legal KB management** — add/edit/disable sources; update KB; **reindex** (chunk → embed → vector upsert → verify); source verification gate | FR-12.1–12.5, UC-036/061/062/080, BR-24 | `knowledge.*` |

### 2.2 Later phases (AI-relevant)

| Phase | Feature | SRS traceability |
|---|---|---|
| Growth (2) | *(no new AI features — broker/messaging/wallet are non-AI)* | — |
| Maturity (3) | AI-assisted **property comparison** | 2.10 / phase 3 |
| Maturity (3) | **Legal-text translation** and comparison against local legislation | 2.10 / phase 3 |
| Maturity (3) | **Law-version management** UI (schema already exists) | FR-12.4, UC-123 |
| Maturity (3) | **AI usage reports/analytics** (contracts analyzed, avg risk, RAG usage, quality) | FR-11.5, UC-121 |
| Maturity (3) | **Legal Q&A** (`answer_query`) and **summarization** (`summarize`) — enum already reserved | AI engine responsibilities (SRS 2.4) |
| Beyond | **OCR** of legacy paper contracts (glossary; no FR yet) | Glossary "OCR" |
| Beyond | **Multi-country laws** | 2.10 |

### 2.3 Non-functional requirements that shape the AI build

| NFR/BR | Requirement | Design consequence |
|---|---|---|
| NFR-1.1 | ≤ **60 s** to generate/analyze a contract | async jobs, never inline |
| NFR-1.4 | **1,000** concurrent users | queue + worker pool, not PHP-FPM blocking |
| NFR-12.1 / BR-27 | show **confidence score** with results | analysis output carries confidence band |
| NFR-12.2 | AI output = assistance, **not** legal opinion / lawyer substitute | UI copy + report disclaimer |
| NFR-12.3 | record **LLM version + KB version** per generation/analysis | `ai_jobs` provenance (already DB-enforced) |
| BR-23 | must consult the KB before generating/analyzing | RAG is mandatory in every pipeline |
| BR-24 | only **verified** sources may be retrieved | filter `is_verified` in every retrieval |
| BR-25 / NFR-12.3 | findings must cite their grounding | `analysis_findings.citations` required |
| BR-28 | **fail closed** if KB unavailable | error → `failed`, return contract to `draft`, notify |

---

## 3. Target architecture

```
 Mobile (Flutter)          Front (Web dashboards)
        │                          │
        └────────── REST (JWT) ────┘
                     │
              Laravel (Back-end)
   ┌──────────────────┼─────────────────────┐
   │  Controllers/Services                 │
   │  AI JobService (enqueue)              │
   │  Outbox Relay worker (dispatch)       │
   │  Inbound Webhook controller (verify)  │
   └──────────────────┼─────────────────────┘
                      │  signed webhook (HMAC, replay-proof)
                      ▼
          AI Legal Engine  (Python, LangGraph/LangChain)
   ┌───────────────────────────────────────────┐
   │  REST API (FastAPI)                       │
   │  Provider abstraction (LLM + embeddings)  │
   │  RAG retriever (pgvector query)           │
   │  Agents: generate_contract, analyze_contract, ... │
   │  Ingestion: chunk → embed → upsert        │
   └───────────────┬───────────────────────────┘
                   │  (AI service holds a `knowledge`-only DB role)
                   ▼
            PostgreSQL (app.* , knowledge.* , ops.*)
              · pgvector embeddings
              · transactional outbox
```

Key contract (already implied by the schema):
1. Laravel writes `app.ai_jobs` (status `queued`) + an `ops.outbox` row in the **same transaction**.
2. The outbox relay POSTs the job payload to the AI service (outbound webhook), marking the job `dispatched`.
3. The AI service runs the LangGraph agent, records usage, and POSTs the result back (inbound signed webhook with a request id + HMAC).
4. Laravel verifies the signature (replay-proof via unique index), writes the result (`contract_versions` + `contract_clauses` and/or `contract_analyses` + `analysis_findings`), and transitions the job to `succeeded`.
5. On failure/timeout → `failed`/`timed_out`, contract returns to `draft` (state machine already allows `under_ai_review → draft`), user notified (BR-28).

---

## 4. Step-by-step implementation plan

### Phase 0 — Decisions & foundations (do first; unblocks everything)

1. **Pin the LLM + embedding providers.** The schema already hardcodes `embedding vector(1536)` and an "LLM provider undecided" open item.
   - Pick the embedding model first: 1536-d → `text-embedding-3-small` (OpenAI/Azure) or equivalent; if a different model is chosen, **edit `000601_*` before seeding** (the migration says so explicitly).
   - Pick the LLM: SRS names "Microsoft Copilot (replaceable)". Decide Azure OpenAI / OpenAI / a hosted Copilot-API. Wrap it behind a provider interface so it is swappable (NFR-9.1 modularity).
2. **Choose the AI service stack.** SRS says LangGraph/LangChain → **Python**. Confirm FastAPI as the HTTP layer.
3. **Resolve the vector-store decision.** The schema already committed to **pgvector in PostgreSQL** (no separate Qdrant/ChromaDB at launch). Ratify that; plan HNSW as a later, measured optimization (comment in `000601_*`).
4. **Decide embeddings DB access for the AI service.** The migration says the AI service holds a Postgres role restricted to `knowledge.*` (it receives contract text over HTTP and must not read `app.contracts`). Create that role + connection.
5. **Define the wire contract** (OpenAPI — NFR-9.2): job request/response schemas for `generate_contract`, `analyze_contract`, and the webhook callback shape; HMAC signing scheme (key, canonical payload, header).
6. **Set up shared config** (`.env`): AI service URL, webhook secret, LLM/embedding credentials, timeouts, retries.

**Exit criteria:** a one-page "AI integration contract" doc + provider config that both Laravel and AI service agree on; embedding dimension finalized.

### Phase 1 — MVP AI Legal Engine (the SRS Phase-1 AI scope)

#### 1A. AI service skeleton
1. Scaffold `AI/` as a Python service (FastAPI + `uv`/`poetry`, LangGraph).
2. Implement a **provider abstraction**: `LLMProvider` (chat/completion) and `EmbeddingProvider`, with a concrete Azure/OpenAI adapter + a fake/deterministic adapter for tests.
3. Add `/health`, `/v1/jobs` (receive), and `/v1/jobs/{id}/callback` (or a single callback endpoint) routes.
4. Add structured logging + per-request trace ids; emit usage metrics (tokens, latency) that later feed UC-121.
5. Add an API key / mutual-auth check for inbound Laravel dispatch (Laravel calls the AI service) and HMAC signing for the outbound callback.

**Acceptance:** service boots; `POST /health` returns 200; a smoke job round-trips.

#### 1B. Ingestion & re-indexing pipeline (FR-12.3, UC-061)
1. Implement **document intake**: from `knowledge.sources`/`documents` (already managed by admin) → load raw text (PDF/DOCX/TXT), compute SHA-256, detect `ar`/`en`.
2. Implement **chunking** with Arabic-aware segmentation (sentence/paragraph boundaries, article numbers as anchors), chunk metadata (`law_type`, effective dates, `article_ref`).
3. Implement **embedding** per chunk (respect `embedding_dimensions` per `kb_versions`).
4. Implement **versioned rebuild**: create a new `kb_versions` row (`building`), upsert chunks, verify counts, flip to `active` atomically (exactly one active per jurisdiction — already DB-enforced), `superseded` the old one. This is the FR-12.3 re-index flow; a half-built version must never serve traffic.
5. Implement **retrieval**: `search(jurisdiction_id, law_type?, query, k, min_score)` → embed query → cosine similarity over `knowledge.chunks` **filtered by `is_verified` (BR-24) and effective dates**, return top-k with chunk text + citation metadata.
6. Add a **reindex trigger**: on KB update (UC-080), enqueue reindex; verify and log (UC-061 step `.60`/`.61`).

**Acceptance:** seed a small Palestinian-law corpus; reindex succeeds end-to-end; retrieval returns correct, cited, verified chunks for a sample query; only the active version is served.

#### 1B′. RAG evaluation & tuning harness (adopt `autoretrieval` as the pattern)

The RAG retrieval is the single highest-risk component (Arabic legal grounding, BR-23/24/25) and the one with the most undecided parameters (embedding model/dimension, chunk size, `k`, keyword filtering). Adopt [`daly2211/autoretrieval`](https://github.com/daly2211/autoretrieval) (MIT) as a **development-time tuning harness** — not as the runtime retriever. It is an "agent experiments on your RAG pipeline and keeps what scores better" loop (Karpathy's autoresearch pattern) with a fixed scoring engine and LLM-generated golden sets.

**What to reuse (high value, portable):**
- `run_eval.py` scoring math + `chunking_eval/utils.py` range helpers — pure character-level overlap (Recall / Precision / IoU / Precision-Omega / F-beta). Language-agnostic; ports directly to Arabic legal text.
- `generate_dataset.py` — LLM-generated (question, ground-truth reference-highlight) pairs from any corpus. Adapt to emit **Arabic legal questions** whose references point at specific law articles.
- `program.md` experiment loop + `results.tsv` log — a disciplined, reproducible change-one-variable → eval → keep/discard protocol.

**What to re-implement for Wathiq (the gaps):**
- **Arabic chunker** — autoretrieval's `SentenceChunker` splits on `[.!?]` (English). Replace with an Arabic-aware chunker: normalize (`app.normalize_arabic` exists in Postgres), split on Arabic/English sentence + article boundaries, anchor chunks to `article_ref`.
- **Production retriever, not Chroma** — autoretrieval scores a ChromaDB pipeline. Instead, implement `get_retrieval_pipeline()` against **pgvector `knowledge.chunks`** with the mandatory filters (`is_verified` BR-24, `jurisdiction_id`, `law_type`, effective dates). The eval then measures the *real* retriever, not a stand-in.
- **Arabic embeddings** — default `text-embedding-3-*` are English-tuned; pick an Arabic-capable embedding model and reconcile with the schema's pinned `embedding_dimensions = 1536`.
- **β choice** — default β=2 favors recall. For legal grounding, missing a governing law is worse than noise (recall), but citing the wrong article is dangerous (precision). Start at **β≈1–1.5** and also watch IoU, not F-beta alone.

**Where this slots into the plan:** it closes open decisions #1 (embedding model/dimension) and #4 (Arabic RAG quality), and adds a **golden-set regression gate** before Phase 1 ships: re-run the eval whenever the chunker/embedding/`k` change and refuse to ship a regression.

#### 1C. Contract generation agent (FR-6.2, UC-047)
1. Build the `generate_contract` LangGraph node/graph:
   - **Retrieve** (1B) using contract context (type, jurisdiction, property, parties) — mandatory (BR-23).
   - **Select jurisdiction law** (FR-6.3): map property/contract jurisdiction → active `kb_versions`.
   - **Draft** the contract with a deterministic, structured output (clauses → `clause_kind` from the DB enum: `parties, subject, price, payment_terms, duration, obligations, warranties, termination, dispute_resolution, governing_law, other`).
   - **Ground** the draft: attach retrieved citations; emit the 14 required clause groups from FR-6.2 (parties, property, subject, obligations, rights, duration, value, payment mechanism, termination, breach, force majeure, dispute resolution, competent court, signatures).
2. Return `{ body, clauses[], citations[], usage }` in the callback.
3. Enforce **fail-closed** (BR-28): if retrieval finds no verified sources or the KB is unreachable → job `failed`, no draft.

**Acceptance:** given a verified sale/rent request, the AI returns a structurally complete Arabic/English draft whose clauses carry citations; no draft is produced without retrieval (test by disabling retrieval).

#### 1D. Contract analysis agent (FR-6.5–6.9, UC-048/049/050)
1. Build the `analyze_contract` LangGraph graph with **structured outputs**:
   - clause completeness (FR-6.5/6.7) → `missing_clause` findings with `suggested_text`.
   - legal conflicts vs. legislation (FR-6.8) → `legal_conflict` findings with the conflicting article citation.
   - ambiguity → `ambiguity`; general improvement → `suggestion`; risk → `risk`.
   - each finding: `kind`, `severity`, `title_ar/en`, `description`, `suggested_text`, `citations[]` (BR-25 — non-empty), `confidence`.
2. Compute **Legal Risk Score** (FR-6.6): integer 0–100, derived from findings (severity-weighted) — deterministic enough to be defensible, with the 5 bands (`very_low … critical`) matching the DB generated column.
3. Produce **summary_ar/en** and the **analysis report** (FR-6.10): summary, contract status, reviewed/proposed/violating clauses, risk score, confidence level, citations, analysis date, model + KB version.
4. Return a structured analysis payload in the callback.

**Acceptance:** for a deliberately flawed draft, the agent returns missing-clause + conflict findings with citations, a correct band, and a confidence level; empty-citation findings are impossible (validated).

#### 1E. Laravel application logic (back-end)
1. **Models + services** for: `AiJob`, `ContractAnalysis`, `AnalysisFinding`, `ContractClause`, `ContractVersion`, `Knowledge` (sources/documents/chunks/kb_versions). (Schema exists; Eloquent models do not.)
2. **`AiJobService::enqueue()`** — create `ai_jobs` row + `ops.outbox` row transactionally; compute `input_hash`.
3. **Outbox relay worker** — claim `ops.outbox` rows (`FOR UPDATE SKIP LOCKED`), POST to the AI service for AI-event types, mark `dispatched`; retry with backoff; timeout → `timed_out` (NFR-1.1 60 s budget).
4. **Inbound webhook controller** — verify HMAC + request id (replay-proof via `ops.webhook_deliveries` unique index), then:
   - on `generate_contract` success → create `contract_versions` (author `ai`) + `contract_clauses`, set `current_version_id`, transition `draft → under_ai_review`.
   - on `analyze_contract` success → create `contract_analyses` + `analysis_findings`, transition `under_ai_review → pending_lawyer_review`.
   - on failure → transition back to `draft` / mark failed, notify.
5. **Lawyer review endpoints** (FR-6.11, UC-028/029/070): list assigned contracts; get analysis + findings; accept/reject each finding (`resolution` + `resolved_by/at/note`); edit clauses → new immutable `contract_versions` (author `lawyer`); approve (BR-29 lawyer gate) → `approved`.
6. **Export** (FR-6.15, UC-059): render contract to PDF (ar/en, RTL-aware), generate the final sealed PDF + `contract_seals`, secure share link.
7. **KB admin endpoints** (FR-12.1/12.2/12.5): CRUD `knowledge.sources`/`documents` with verification workflow (BR-24), triggering reindex (1B).
8. **Provenance + audit** (NFR-12.3, FR-6.14): populate `ai_jobs.provider/model_id/model_version/kb_version_id` on completion (DB already refuses a succeeded job without them); write `audit_logs` for every transition.

**Acceptance:** end-to-end happy path (request accepted → AI draft → AI analysis → lawyer edits + approves → signed) runs entirely async with correct state transitions; a replayed webhook is rejected; a killed AI service fails the job closed and notifies.

#### 1F. Client surfaces (minimum to exercise the loop)
1. **Mobile (Flutter):** contract list/detail, AI draft view, analysis view (risk score + findings with accept/reject for lawyer role), lawyer review screen, signature, export/PDF.
2. **Front (web):** admin KB-management console (sources, verification, reindex status) and lawyer review dashboard.
3. All UI shows the **NFR-12.2 disclaimer** ("AI assistance, not a legal opinion") and **confidence** (NFR-12.1/BR-27).

**Exit criteria (Phase 1 done):** a complete AI contract lifecycle runs on Palestinian law, grounded in a verified KB, with lawyer-gated approval, provenance, and audit — i.e. SRS Phase-1 AI scope (2.9 bullet "AI-drafted contracts analyzed against a local-law KB, routed to a lawyer").

### Phase 2 — Growth (no new AI; unblock integrations)
- Broker delegation, messaging, advanced wallet/payouts, commissions, disputes, analytics dashboard (per SRS 2.10 phase 2). The AI system only needs to keep serving contracts under the now-delegated broker role (ensure `ai_jobs.requested_by` and contract author tracking cover broker-delegated flows).

### Phase 3 — Maturity (additional AI)
1. **AI usage reports** (FR-11.5, UC-121): aggregate `ai_jobs` + `contract_analyses` (contracts analyzed, avg risk score, RAG usage, tokens, latency, quality/accuracy) → admin dashboard + PDF/Excel export (UC-122).
2. **AI-assisted property comparison** (2.10): embed property attributes, surface similarity + side-by-side diff.
3. **Legal-text translation + legislation comparison** (2.10): translate contract ↔ language and diff against active law versions.
4. **Law-version management UI** (FR-12.4, UC-123): expose `kb_versions` lifecycle to admins.
5. **Legal Q&A + summarization** (`answer_query`, `summarize`): a RAG-grounded Q&A endpoint over the KB, plus contract summarization — both enum kinds are already reserved.

### Beyond current scope
- OCR of legacy paper contracts (add an ingestion pre-processor; extend `documents.raw_path`).
- Additional countries' laws (add `jurisdictions` + per-country KB versions — schema already supports it).
- Government ownership-registry + insurance integrations.

---

## 5. Recommended build order (dependency-ordered summary)

1. Phase 0 decisions (provider, embedding dim, wire contract).
2. AI service skeleton (1A).
3. Ingestion + retrieval (1B) — this is the dependency for everything else.
4. Generation agent (1C) → Laravel enqueue + webhook callback + version write (1E items 1–4) → show a draft end-to-end.
5. Analysis agent (1D) → findings/risk write + lawyer review (1E items 4–5) → approval gate.
6. Export/seals (1E item 6) → client surfaces (1F) → KB admin (1E item 7).
7. Harden (retries, replay, timeout, observability, audit) and measure against NFR-1.1/NFR-1.4.

---

## 6. Open decisions & risks (raise with the team)

| # | Decision | Impact |
|---|---|---|
| 1 | **Embedding model + dimension** (schema pins 1536) | Must finalize before seeding; wrong dim = full re-embed. **Resolve empirically with the autoretrieval eval harness (§1B′) on an Arabic corpus.** |
| 2 | **LLM provider** (Microsoft Copilot vs. Azure OpenAI vs. other) | Cost, Arabic quality, data-residency for legal text |
| 3 | **AI service language** (Python per LangGraph) | Confirm vs. a Node/TS option |
| 4 | **Arabic RAG quality** | Arabic chunking/embeddings need evaluation; budget for a golden-set eval. **autoretrieval's scoring + dataset generator is the harness for this; adapt chunker to Arabic and retriever to pgvector.** |
| 5 | **Risk-score determinism** | A "legal risk score" that renders inconsistently is indefensible (schema comment); need a versioned, tested scoring rubric |
| 6 | **Webhook auth** | HMAC + request id replay defense is already designed in `ops.webhook_deliveries`; confirm key rotation |
| 7 | **Lawyer review UX for findings** | Accept/reject per finding is in schema; needs UI workflow definition |
| 8 | **Confidence score source** (NFR-12.1 "if available") | LLM logprobs vs. retrieval score vs. heuristic — decide and document |

---

## 7. Files to read before coding

- `Back-end/wathiq/database/migrations/2026_08_04_000601_create_knowledge_base_tables.php` (KB + pgvector, open items)
- `..._000602_create_ai_jobs_table.php` (async boundary + provenance)
- `..._000603/_000604_*` (analyses + findings)
- `..._000502/_000503/_000505_*` (versions, clauses, state machine)
- `..._001002_create_ops_outbox_table.php` (outbox + signed webhook)
- `wathiq_SRS_V05.pdf` — FR-6.x, FR-12.x, BR-23–28, NFR-1.x/NFR-12.x, UC-008/009/027–030/036/047–050/057/059/061/062/070/080/121.
