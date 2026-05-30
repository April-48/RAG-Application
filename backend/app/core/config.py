"""App settings — loaded from .env / environment variables.

Stuff like DATABASE_URL, JWT secret, embedding provider, Redis toggle, upload
folder path. Call get_settings() once; it's cached.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from the environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Postgres connection string (docker-compose default below) ---
    database_url: str = (
        "postgresql+psycopg://postgres:password@localhost:5432/rag_app"
    )

    # --- JWT login tokens ---
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- Embeddings: local (free) vs OpenAI. EMBEDDING_DIM must match pgvector column! ---
    #   local  all-MiniLM-L6-v2        -> 384
    #   openai text-embedding-3-small -> 1536 (need migration + re-ingest)
    embedding_provider: str = "local"  # "local" | "openai"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # --- Chat LLM — OpenAI by default; any OpenAI-compatible URL works too ---
    openai_api_key: str = ""
    llm_provider: str = "openai"  # "openai" | "openai-compatible"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    # How many chunks we pull from pgvector per question.
    retrieval_top_k: int = 5

    # --- Optional Redis answer cache — app still works if Redis is off/down ---
    redis_url: str = "redis://localhost:6379/0"
    enable_redis_cache: bool = False
    cache_ttl_seconds: int = 3600

    # Where uploaded files live on disk: {upload_dir}/{user_id}/{document_id}/
    upload_dir: str = "backend/storage/uploads"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
