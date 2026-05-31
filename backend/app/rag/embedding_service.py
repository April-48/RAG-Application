"""Embedder interface — local sentence-transformers or OpenAI.

The RAG pipeline only talks to the Embedder protocol, not a specific vendor.
That makes it easy to swap providers via EMBEDDING_PROVIDER in .env.

EMBEDDING_DIM must match the pgvector column width (384 for local MiniLM by
default). A mismatch raises EmbeddingError at model load time.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.core.config import get_settings
from app.core.exceptions import EmbeddingError


# Minimal interface the ingestion and retrieval pipeline depends on.
@runtime_checkable
class Embedder(Protocol):

    # Vector size this embedder produces — must match pgvector column width.
    @property
    def dimension(self) -> int:
        ...

    # Embed many strings at once during ingestion batches.
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    # Embed a single question string for retrieval.
    def embed_query(self, text: str) -> list[float]:
        ...


# Embeddings via sentence-transformers — runs locally with no API key.
# I load the model lazily on first use so imports stay cheap.
class LocalMiniLMEmbeddingService:

    # Configure local model name and expected vector dimension from settings.
    def __init__(
        self, model_name: str | None = None, expected_dim: int | None = None
    ) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.expected_dim = expected_dim or settings.embedding_dim
        self._model = None

    # Lazy-load sentence-transformers and verify dimension matches config.
    # Raises EmbeddingError when the package is missing or dims disagree.
    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - depends on env
                raise EmbeddingError(
                    "sentence-transformers is not installed"
                ) from exc

            model = SentenceTransformer(self.model_name)
            dim = model.get_sentence_embedding_dimension()
            if dim != self.expected_dim:
                raise EmbeddingError(
                    f"Model '{self.model_name}' produces {dim}-dim vectors but "
                    f"embedding_dim is configured as {self.expected_dim}"
                )
            self._model = model
        return self._model

    # Configured embedding dimension for local MiniLM.
    @property
    def dimension(self) -> int:
        return self.expected_dim

    # Encode strings with sentence-transformers (normalized vectors).
    # Raises EmbeddingError on model or runtime failures.
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            model = self._load()
            vectors = model.encode(
                list(texts), normalize_embeddings=True, convert_to_numpy=True
            )
        except EmbeddingError:
            raise
        except Exception as exc:  # pragma: no cover - runtime model failures
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc
        return [vector.tolist() for vector in vectors]

    # Embed a single question string for retrieval.
    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


# Embeddings via the OpenAI API (e.g. text-embedding-3-small).
# I create the client lazily and raise EmbeddingError when setup fails.
class OpenAIEmbeddingService:

    # Configure OpenAI embedding model, dimension, and API key from settings.
    def __init__(
        self,
        model_name: str | None = None,
        expected_dim: int | None = None,
        api_key: str | None = None,
    ) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.expected_dim = expected_dim or settings.embedding_dim
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self._client = None

    # Create the OpenAI client on first use.
    # Raises EmbeddingError when the API key or openai package is missing.
    def _get_client(self):
        if not self.api_key:
            raise EmbeddingError("OPENAI_API_KEY is not configured")
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - depends on env
                raise EmbeddingError("openai package is not installed") from exc
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    # Configured embedding dimension for OpenAI.
    @property
    def dimension(self) -> int:
        return self.expected_dim

    # Call OpenAI embeddings API for a batch of strings.
    # Raises EmbeddingError on network or API failures.
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        # text-embedding-3-* lets you pass dimensions=; older models ignore it.
        kwargs: dict = {}
        if self.model_name.startswith("text-embedding-3"):
            kwargs["dimensions"] = self.expected_dim
        try:
            response = client.embeddings.create(
                model=self.model_name, input=list(texts), **kwargs
            )
        except Exception as exc:  # pragma: no cover - network/runtime failures
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc
        return [item.embedding for item in response.data]

    # Embed one question via OpenAI.
    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


# Return the cached embedding provider selected by EMBEDDING_PROVIDER.
# The underlying model loads lazily on first embed, so this call is cheap.
# Raises EmbeddingError when the provider name is unknown.
@lru_cache
def get_embedding_service() -> Embedder:
    settings = get_settings()
    provider = (settings.embedding_provider or "local").lower()
    if provider in {"local", "sentence-transformers", "sentence_transformers", "st"}:
        return LocalMiniLMEmbeddingService()
    if provider in {"openai", "openai-compatible"}:
        return OpenAIEmbeddingService()
    raise EmbeddingError(
        f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider!r} "
        "(expected 'local' or 'openai')"
    )
