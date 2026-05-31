"""LLM wrapper — OpenAI or any OpenAI-compatible chat endpoint.

get_llm_service() reads LLM_MODEL, LLM_BASE_URL, and OPENAI_API_KEY from
settings. Works with OpenAI, OpenRouter, Ollama, vLLM, etc. when the server
speaks the OpenAI chat completions API.

Temperature is omitted by default so models like gpt-5-mini that only accept the
provider default still work. Set LLM_TEMPERATURE in .env when your model supports it.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.core.config import get_settings
from app.core.exceptions import LLMError


# Minimal chat interface — one-shot and streaming generation.
@runtime_checkable
class LLM(Protocol):

    # Return the full assistant reply for a chat message list.
    def generate(self, messages: list[dict[str, str]]) -> str:
        ...

    # Yield assistant reply tokens one at a time.
    def generate_stream(
        self, messages: list[dict[str, str]]
    ) -> Iterator[str]:
        ...


# Chat completions via OpenAI or any OpenAI-compatible endpoint.
# When base_url is set, I allow missing API keys for local providers.
class OpenAILLMService:

    # Read model name, API key, and optional base URL from settings.
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.base_url = (
            base_url if base_url is not None else (settings.llm_base_url or None)
        )
        self.temperature = settings.llm_temperature
        self._client = None

    # Lazy-create the OpenAI client — works with OpenAI or compatible servers.
    # Raises LLMError when the API key and base URL are both missing.
    def _get_client(self):
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

    def _completion_kwargs(self, *, stream: bool) -> dict:
        kwargs: dict = {
            "model": self.model,
            "messages": [],  # filled by caller
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if stream:
            kwargs["stream"] = True
        return kwargs

    # Non-streaming chat completion — returns full assistant text.
    # Raises LLMError on network or API failures.
    def generate(self, messages: list[dict[str, str]]) -> str:
        client = self._get_client()
        kwargs = self._completion_kwargs(stream=False)
        kwargs["messages"] = messages
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:  # pragma: no cover - network/runtime failures
            raise LLMError(f"LLM request failed: {exc}") from exc

        content = response.choices[0].message.content
        return (content or "").strip()

    # Stream chat completion tokens one at a time for SSE.
    # Raises LLMError on network or API failures.
    def generate_stream(
        self, messages: list[dict[str, str]]
    ) -> Iterator[str]:
        client = self._get_client()
        kwargs = self._completion_kwargs(stream=True)
        kwargs["messages"] = messages
        try:
            stream = client.chat.completions.create(**kwargs)
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:  # pragma: no cover - network/runtime failures
            raise LLMError(f"LLM request failed: {exc}") from exc


# Return the cached LLM provider selected by LLM_PROVIDER in settings.
# Defaults to OpenAI; openai-compatible aliases use LLM_BASE_URL.
# Raises LLMError when the provider name is unknown.
@lru_cache
def get_llm_service() -> LLM:
    settings = get_settings()
    provider = (settings.llm_provider or "openai").lower()
    if provider in {"openai", "openai-compatible", "openrouter", "ollama", "vllm"}:
        return OpenAILLMService()
    raise LLMError(
        f"Unknown LLM_PROVIDER: {settings.llm_provider!r} "
        "(expected 'openai' or 'openai-compatible')"
    )
