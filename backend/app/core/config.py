"""
Application configuration.

Why this file exists:
- Centralizes all environment-driven settings (12-factor style).
- Avoids scattered os.getenv() calls across the codebase.
- Makes local/dev/prod configuration consistent and typed.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime settings loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI_GOVERNANCE"
    app_env: str = "development"
    debug: bool = True

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"

    database_url: str = (
        "postgresql+psycopg2://ai_governance:ai_governance_dev@127.0.0.1:5433/ai_governance"
    )

    jwt_secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""

    # Fernet key material for BYOK provider credentials (falls back to jwt_secret_key).
    credential_encryption_key: str = ""

    # RAG: local hashed embeddings by default (reliable offline); OpenAI optional.
    rag_prefer_openai_embeddings: bool = False
    openai_embedding_model: str = "text-embedding-3-small"
    # Use pgvector ANN when extension + 384-d local embeddings are available.
    rag_use_pgvector: bool = True

    # Agents: try LLM JSON planner when a provider key is available; always fall back to heuristics.
    agents_use_llm_planner: bool = True

    # API rate limiting (in-memory sliding window; per process).
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_llm_requests: int = 30
    rate_limit_llm_window_seconds: int = 60

    # Scheduled retention purge (daemon thread; only orgs with auto_purge enabled).
    retention_scheduler_enabled: bool = True
    retention_scheduler_interval_seconds: int = 3600
    retention_scheduler_initial_delay_seconds: int = 30

    # Webhook delivery retries (pending rows + background worker).
    webhook_max_attempts: int = 3
    webhook_retry_base_seconds: int = 30
    webhook_retry_worker_enabled: bool = True
    webhook_retry_worker_interval_seconds: int = 15
    webhook_retry_worker_initial_delay_seconds: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings singleton.

    Why cached: settings are immutable for process lifetime; avoid re-reading .env.
    """
    return Settings()
