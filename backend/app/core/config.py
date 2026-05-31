"""App settings — loaded from .env / environment variables.

Stuff like DATABASE_URL, JWT secret, embedding provider, Redis toggle, upload
folder path. Call get_settings() once; it's cached.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


# I load every runtime knob from the environment or a local `.env` file.
# Pydantic validates types and gives me one object the rest of the app imports.
class Settings(BaseSettings):
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
    # Default gpt-5-mini for document-grounded RAG; override via LLM_MODEL in .env.
    openai_api_key: str = ""
    llm_provider: str = "openai"  # "openai" | "openai-compatible"
    llm_model: str = "gpt-5-mini"
    llm_base_url: str = ""
    # Omit from API requests when unset — gpt-5-mini only supports the provider default.
    # Set LLM_TEMPERATURE=0 in .env for models like gpt-4o-mini that allow it.
    llm_temperature: float | None = None
    # How many chunks we pull from pgvector per question.
    retrieval_top_k: int = 8
    # Minimum cosine similarity (1 - pgvector distance) when enforcement is on.
    retrieval_min_similarity: float = 0.20
    # When False (MVP default), I still send top-k chunks to the LLM if pgvector
    # returns any hits — the LLM prompt handles "not enough context" instead of
    # blocking here. Set True to pre-filter weak semantic matches.
    retrieval_enforce_similarity_threshold: bool = False

    # --- Optional Redis answer cache — app still works if Redis is off/down ---
    redis_url: str = "redis://localhost:6379/0"
    enable_redis_cache: bool = False
    cache_ttl_seconds: int = 3600

    # --- Optional Redis chat rate limit — fail-open if Redis is off/down ---
    enable_rate_limit: bool = False
    chat_rate_limit_per_minute: int = 10

    # Where uploaded files live on disk: {upload_dir}/{user_id}/{document_id}/
    upload_dir: str = "backend/storage/uploads"
    # Maximum upload size in megabytes (extension + content validated separately).
    max_upload_size_mb: int = 20

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


# I cache Settings so every import shares one parsed config object.
# Call this at startup or in module scope — do not construct Settings() directly.
@lru_cache
def get_settings() -> Settings:
    return Settings()
