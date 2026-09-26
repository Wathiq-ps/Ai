# Wathiq AI Legal Engine

FastAPI service, scaffolded per `WATHIQ_AI_SPRINT_PLAN.md` Catch-Up Sprint 1A.
See `WATHIQ_AI_SPRINT_PLAN.md`'s Phase 0 section for the provider/stack decisions
and `openapi.yaml` for the wire contract with the Laravel back-end.

## Run

```bash
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8001
```

`GET /health` → `{"status": "ok"}`. Without `DEEPINFRA_API_KEY`/`OPENROUTER_API_KEY`
set, provider calls fall back to deterministic fakes (`app/providers/fake.py`) —
fine for local dev and required for the test suite.

## Test

```bash
uv run pytest
```

## Layout

- `app/main.py` — routes, trace-id + timing middleware, signed callback delivery
- `app/jobs.py` — one interface per job kind (payload model, preflight, runner,
  prompt version, budget); the wire `kind` enum is read off that table
- `app/wire.py` — the contract with Laravel declared once: payload models, the
  `error_code` enum, and the callback envelope. Held to `openapi.yaml` by
  `tests/test_wire_contract.py`
- `app/config.py` — env-driven settings
- `app/security.py` — outbound HMAC signing of callbacks
- `app/providers/` — `LLMProvider`/`EmbeddingProvider`/`RerankProvider`
  interfaces; fake adapters plus one real OpenAI-compatible adapter used
  against OpenRouter (embeddings: nemotron-3-embed-1b) and DeepSeek (LLM)
- `app/knowledge.py` — ingestion, versioned KB rebuild, retrieval (1B)
- `app/generate_contract.py` — drafting agent (1C)
- `app/analyze_contract.py` — analysis agent + risk score (1D)
- `app/reindex.py` — UC-080 rebuild of a jurisdiction's KB version

`/v1/jobs` accepts `generate_contract`, `analyze_contract` and `reindex`; each
runs as a background task and POSTs an HMAC-signed callback to Laravel.

Not built yet: `answer_query`/`summarize` (Phase 3), the RAG eval harness
(golden set), callback retry/redelivery.

## Blocked

`knowledge.sources.is_verified` can only be set with a `verified_by` pointing
at `app.users`, which the `wathiq_ai` role cannot read — so verification is a
Laravel admin act. Until the four seeded West Bank sources are verified there,
`search()` returns nothing (BR-24) and both agents correctly fail closed.
