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

- `app/main.py` — routes, trace-id + timing middleware
- `app/config.py` — env-driven settings
- `app/security.py` — inbound API-key check, outbound HMAC signing
- `app/providers/` — `LLMProvider`/`EmbeddingProvider` interfaces; fake adapters
  plus one real OpenAI-compatible adapter used against both DeepInfra
  (embeddings: Qwen3-Embedding-8B) and OpenRouter (LLM: DeepSeek-V4-Pro)

Not built yet: LangGraph agents (`generate_contract`/`analyze_contract`, Phase
1C/1D), ingestion/retrieval (1B), the real `/v1/jobs/{id}/callback` dispatch to
Laravel.
