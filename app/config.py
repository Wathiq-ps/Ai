from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded from env vars / .env — see WATHIQ_AI_SPRINT_PLAN.md's Phase 0 section."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # NFR-1.1: a contract must be generated/analysed within 60s. Reindex is
    # deliberately not bounded by this — a full-corpus rebuild is minutes.
    job_timeout_seconds: float = 60.0
    ai_webhook_secret: str = ""
    laravel_callback_url: str = "http://localhost:8000/api/v1/ai/callback"

    # Postgres — the `wathiq_ai` restricted role (knowledge.* only, see
    # 2026_08_04_990000_grant_wathiq_privileges.php). Blank = get_pool() raises.
    database_url: str = ""

    # OpenRouter — embeddings + reranker, both free-tier. Embeddings are
    # OpenAI-compatible; rerank is OpenRouter's own /rerank endpoint (see
    # app/providers/openrouter_rerank.py). Free tier logs prompts/output and
    # is "trial use only" — fine for dev/eval, not for real client contracts.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    embedding_model: str = "nvidia/nemotron-3-embed-1b:free"
    embedding_dimensions: int = 1536  # truncated from the model's native 2048
    # What the endpoint is actually asked for; nemotron-3-embed-1b accepts only
    # its native 2048, so truncation to embedding_dimensions happens client-side.
    embedding_native_dimensions: int = 2048
    rerank_model: str = "nvidia/llama-nemotron-rerank-vl-1b-v2:free"

    # DeepSeek — LLM, direct platform API (OpenAI-compatible), not OpenRouter.
    #
    # A non-reasoning model on purpose. Measured on the demo lease, one analyze
    # prompt, same excerpts: deepseek-v4-pro 47-137s (8.5k reasoning tokens),
    # deepseek-v4-flash 51-55s (9.2k reasoning tokens), deepseek-chat 11-17s
    # (no reasoning tokens). The reasoning models spend ~85% of their output
    # budget thinking and blow NFR-1.1's 60s on their own, before the repair
    # loop or a second sample. deepseek-chat leaves enough budget to run the
    # 3-sample vote (measured 36s end to end), and the vote buys back more
    # stability than the reasoning models were providing — it drops the
    # one-off findings they each invented on a different run.
    #
    # Since DeepSeek-V4.1 (checked 2026-09-26) `deepseek-chat` is only a legacy
    # alias: the API answers it as `deepseek-flash` with thinking off, and
    # /models lists just deepseek-flash and deepseek-v4-pro. So we name the
    # real model, which also reads images (see DOCUMENT_IMAGES.md). Its default
    # is thinking ON — a one-line reply spent 106 reasoning tokens — so
    # get_llm_provider() turns thinking off explicitly to keep the budget above.
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    chat_model: str = "deepseek-flash"


settings = Settings()
