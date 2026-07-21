"""LLM completion request/response schemas."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

ProviderName = Literal["groq", "gemini", "openai", "claude"]


class CompletionRequest(BaseModel):
    """Body for POST /api/v1/llm/completions."""

    prompt: str = Field(..., min_length=1, max_length=32000)
    provider: ProviderName = "groq"
    model: str | None = Field(
        default=None,
        description="Model id. Defaults per provider when omitted.",
        examples=["llama-3.1-8b-instant"],
    )
    organization_slug: str = Field(default="default", max_length=100)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=1, le=8192)


class CompletionResponse(BaseModel):
    """Completion payload including usage + cost metadata."""

    history_id: str
    provider: str
    model: str
    prompt: str
    response: str | None
    status: str
    error_message: str | None = None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: Decimal | None
    latency_ms: int | None
    organization_slug: str
    arena_run_id: str | None = None
