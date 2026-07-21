"""
Shared provider completion contract.

Why this exists:
- OpenAI / Claude / Gemini adapters all return the same shape.
- Arena and single-completion services stay provider-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCompletionResult:
    """Normalized completion payload from any LLM provider."""

    provider: str
    model: str
    response_text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
