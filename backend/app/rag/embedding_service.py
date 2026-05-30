"""Embedder interface — local sentence-transformers or OpenAI.

Pipeline only talks to Embedder, not a specific vendor. EMBEDDING_DIM must match
the pgvector column (384 for local MiniLM by default).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.core.config import get_settings
from app.core.exceptions import EmbeddingError


@runtime_checkable
class Embedder(Protocol):
    """Minimal interface the ingestion + retrieval pipeline depends on."""

    @property
    def dimension(self) -> int:
        """Vector size produced by this embedder."""
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed many strings at once (ingestion batches)."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single question for retrieval."""
        ...


class LocalMiniLMEmbeddingService:
    """Embeddings via sentence-transformers (runs locally, no API key).

    The model is loaded lazily (on first use) so importing this module stays
    cheap, and its dimension is validated against ``embedding_dim``.
    """

    def __init__(
        self, model_name: str | None = None, expected_dim: int | None = None
    ) -> None:
        """Configure local model name and expected vector dimension from settings."""
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.expected_dim = expected_dim or settings.embedding_dim
        self._model = None

    def _load(self):
        """Lazy-load sentence-transformers model and verify dimension matches config."""
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

    @property
    def dimension(self) -> int:
        """Configured embedding dimension for local MiniLM."""
        return self.expected_dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Encode strings with sentence-transformers (normalized vectors)."""
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

    def embed_query(self, text: str) -> list[float]:
        """Embed a single question string for retrieval."""
        return self.embed_texts([text])[0]


class OpenAIEmbeddingService:
    """Embeddings via the OpenAI API (e.g. ``text-embedding-3-small``).

    The client is created lazily and a clear `EmbeddingError` is raised if the
    API key or package is missing.
    """

    def __init__(
        self,
        model_name: str | None = None,
        expected_dim: int | None = None,
        api_key: str | None = None,
    ) -> None:
        """Configure OpenAI embedding model, dimension, and API key from settings."""
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.expected_dim = expected_dim or settings.embedding_dim
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self._client = None

    def _get_client(self):
        """Create OpenAI client on first use — raises if API key missing."""
        if not self.api_key:
            raise EmbeddingError("OPENAI_API_KEY is not configured")
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - depends on env
                raise EmbeddingError("openai package is not installed") from exc
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    @property
    def dimension(self) -> int:
        """Configured embedding dimension for OpenAI."""
        return self.expected_dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Call OpenAI embeddings API for a batch of strings."""
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

    def embed_query(self, text: str) -> list[float]:
        """Embed one question via OpenAI."""
        return self.embed_texts([text])[0]


@lru_cache
def get_embedding_service() -> Embedder:
    """Return the cached embedding provider selected by ``EMBEDDING_PROVIDER``.

    The underlying model/client loads lazily on first embed, so this is cheap to
    call. Defaults to the local sentence-transformers model; use ``openai`` for
    the OpenAI provider.
    """
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
