"""Arena Mode request/response schemas."""

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.llm import CompletionResponse, ProviderName


class ArenaParticipantRequest(BaseModel):
    provider: ProviderName
    model: str | None = Field(
        default=None,
        description="Optional model override for this participant",
    )


class ArenaRunRequest(BaseModel):
    """Body for POST /api/v1/arena/runs."""

    prompt: str = Field(..., min_length=1, max_length=32000)
    participants: list[ArenaParticipantRequest] = Field(..., min_length=2, max_length=6)
    organization_slug: str = Field(default="default", max_length=100)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=1, le=8192)


class ArenaRunResponse(BaseModel):
    arena_run_id: str
    prompt: str
    organization_slug: str
    results: list[CompletionResponse]
    total_estimated_cost_usd: Decimal | None
    success_count: int
    error_count: int
