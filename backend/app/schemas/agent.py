"""AI agent request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


AVAILABLE_TOOLS = (
    "classify_task",
    "rag_search",
    "llm_answer",
    "rag_answer",
)


class AgentDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[str] = Field(
        default_factory=lambda: ["classify_task", "rag_search", "llm_answer"],
        min_length=1,
        max_length=8,
    )
    default_provider: str = Field(default="groq", max_length=50)
    default_model: str | None = None
    max_steps: int = Field(default=8, ge=1, le=12)
    organization_slug: str = Field(default="default", max_length=100)


class AgentDefinitionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    organization_slug: str
    name: str
    description: str | None
    steps: list[str]
    default_provider: str
    default_model: str | None
    max_steps: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentRunRequest(BaseModel):
    definition_id: UUID
    input_text: str = Field(..., min_length=1, max_length=8000)
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = None
    organization_slug: str = Field(default="default", max_length=100)


class AgentPlanRunRequest(BaseModel):
    """Free-form goal → planner chooses tools → same sequential runner."""

    goal: str = Field(..., min_length=1, max_length=8000)
    provider: str | None = Field(default="groq", max_length=50)
    model: str | None = None
    organization_slug: str = Field(default="default", max_length=100)


class AgentPlanPreviewResponse(BaseModel):
    goal: str
    tools: list[str]
    rationale: str
    planner: str = Field(
        default="heuristic_v1",
        description="Planner used: heuristic_v1 or llm_v1",
    )


class AgentStepLogItem(BaseModel):
    step: int
    tool: str
    status: str
    summary: str
    detail: dict | None = None


class AgentRunResponse(BaseModel):
    id: UUID
    definition_id: UUID
    definition_name: str
    organization_slug: str
    input_text: str
    status: str
    output_text: str | None
    error_message: str | None
    steps_log: list[AgentStepLogItem]
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentToolCatalogResponse(BaseModel):
    tools: list[str]
