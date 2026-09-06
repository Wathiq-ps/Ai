from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded from env vars / .env — see WATHIQ_AI_SPRINT_PLAN.md's Phase 0 section."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ai_service_api_key: str = ""
    ai_webhook_secret: str = ""
    laravel_callback_url: str = "http://localhost:8000/api/ai/callback"

    # Postgres — the `wathiq_ai` restricted role (knowledge.* only, see
    # 2026_08_04_990000_grant_wathiq_privileges.php). Blank = get_pool() raises.
    database_url: str = ""

    # OpenRouter — embeddings + reranker, both free-tier. Embeddings are
    # OpenAI-compatible; rerank is OpenRouter's own /rerank endpoint (see
    # app/providers/openrouter_rerank.py). Free tier logs prompts/output and
    # is "trial use only" — fine for dev/eval, not for real client contracts.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    embedding_model: str = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
    embedding_dimensions: int = 1536  # truncated from the model's native 2048
    rerank_model: str = "nvidia/llama-nemotron-rerank-vl-1b-v2:free"

    # DeepSeek — LLM, direct platform API (OpenAI-compatible), not OpenRouter.
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    chat_model: str = "deepseek-v4-pro"


settings = Settings()
