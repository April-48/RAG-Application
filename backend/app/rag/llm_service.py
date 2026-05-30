"""LLM wrapper — OpenAI or any OpenAI-compatible endpoint.

get_llm_service() reads LLM_MODEL / LLM_BASE_URL from settings.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.core.config import get_settings
from app.core.exceptions import LLMError


@runtime_checkable
class LLM(Protocol):
    """Minimal chat interface — one-shot and streaming generation."""

    def generate(self, messages: list[dict[str, str]]) -> str:
        """Return full assistant reply for a chat message list."""
        ...

    def generate_stream(
        self, messages: list[dict[str, str]]
    ) -> Iterator[str]:
        """Yield assistant reply tokens one at a time."""
        ...


class OpenAILLMService:
    """Chat completions via OpenAI or any OpenAI-compatible endpoint.

    When ``base_url`` is set (e.g. OpenRouter/Ollama) an API key is optional, so
    local providers that don't require one still work.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Read model name, API key, and optional base URL from settings."""
        settings = get_settings()
        self.model = model or settings.llm_model
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.base_url = (
            base_url if base_url is not None else (settings.llm_base_url or None)
        )
        self._client = None

    def _get_client(self):
        """Lazy-create OpenAI client — works with OpenAI or compatible local servers."""
        if self._client is None:
            # Real OpenAI needs a key; local OpenAI-compatible servers often don't.
            if not self.api_key and not self.base_url:
                raise LLMError("OPENAI_API_KEY is not configured")
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - depends on env
                raise LLMError("openai package is not installed") from exc
            self._client = OpenAI(
                api_key=self.api_key or "not-needed", base_url=self.base_url
            )
        return self._client

    def generate(self, messages: list[dict[str, str]]) -> str:
        """Non-streaming chat completion — returns full assistant text."""
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
            )
        except Exception as exc:  # pragma: no cover - network/runtime failures
            raise LLMError(f"LLM request failed: {exc}") from exc

        content = response.choices[0].message.content
        return (content or "").strip()

    def generate_stream(
        self, messages: list[dict[str, str]]
    ) -> Iterator[str]:
        """Stream chat completion tokens one at a time for SSE."""
        client = self._get_client()
        try:
            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:  # pragma: no cover - network/runtime failures
            raise LLMError(f"LLM request failed: {exc}") from exc


@lru_cache
def get_llm_service() -> LLM:
    """Return the cached LLM provider selected by ``LLM_PROVIDER``.

    Defaults to OpenAI. ``openai-compatible`` (and aliases) use the same OpenAI
    client pointed at ``LLM_BASE_URL``.
    """
    settings = get_settings()
    provider = (settings.llm_provider or "openai").lower()
    if provider in {"openai", "openai-compatible", "openrouter", "ollama", "vllm"}:
        return OpenAILLMService()
    raise LLMError(
        f"Unknown LLM_PROVIDER: {settings.llm_provider!r} "
        "(expected 'openai' or 'openai-compatible')"
    )
