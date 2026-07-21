"""
Provider client factory.

Why this exists:
- Single switch for groq/gemini/openai/claude used by LLM + Arena services.
- Optional api_key enables BYOK (org credential) without changing adapters.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.core.exceptions import ValidationAppError
from app.integrations.base import ProviderCompletionResult
from app.integrations.claude_client import ClaudeClient
from app.integrations.gemini_client import GeminiClient
from app.integrations.groq_client import GroqClient
from app.integrations.openai_client import OpenAIClient
from app.services.cost_estimator import DEFAULT_MODELS

SUPPORTED_PROVIDERS = frozenset(DEFAULT_MODELS.keys())


def resolve_model(provider: str, model: str | None) -> str:
    """Return the requested model or the provider default."""
    if model and model.strip():
        return model.strip()
    return DEFAULT_MODELS[provider]


def call_provider(
    *,
    provider: str,
    prompt: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    api_key: str | None = None,
) -> ProviderCompletionResult:
    """Dispatch a completion to the correct provider adapter."""
    if provider == "groq":
        return GroqClient(api_key=api_key).complete(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if provider == "gemini":
        return GeminiClient(api_key=api_key).complete(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if provider == "openai":
        return OpenAIClient(api_key=api_key).complete(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if provider == "claude":
        return ClaudeClient(api_key=api_key).complete(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    raise ValidationAppError(
        f"Unsupported provider '{provider}'. Supported: {sorted(SUPPORTED_PROVIDERS)}",
        details={"provider": provider},
    )


def call_provider_stream(
    *,
    provider: str,
    prompt: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    api_key: str | None = None,
) -> Iterator[str | ProviderCompletionResult]:
    """
    Yield text deltas then a final ProviderCompletionResult.

    Groq/OpenAI use native streaming. Claude/Gemini fall back to one buffered chunk.
    """
    if provider == "groq":
        yield from GroqClient(api_key=api_key).complete_stream(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return
    if provider == "openai":
        yield from OpenAIClient(api_key=api_key).complete_stream(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return

    result = call_provider(
        provider=provider,
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
    )
    if result.response_text:
        yield result.response_text
    yield result
