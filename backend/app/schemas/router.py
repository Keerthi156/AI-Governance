"""Intelligent Task Router request/response schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.llm import CompletionResponse

TaskType = Literal[
    "coding",
    "summarization",
    "creative",
    "qa",
    "analysis",
    "translation",
    "chat",
    "general",
]
Preference = Literal["balanced", "cost", "speed", "quality"]


class ClassifyRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=32000)


class ClassifyResponse(BaseModel):
    task_type: TaskType
    confidence: float
    matched_signals: list[str]
    scores: dict[str, float]


class RouteCandidateItem(BaseModel):
    provider: str
    model: str
    score: float
    available: bool
    reason: str


class RouteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=32000)
    preference: Preference = "balanced"
    organization_slug: str = Field(default="default", max_length=100)
    execute: bool = False
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=1, le=8192)


class RouteResponse(BaseModel):
    decision_id: str
    task_type: TaskType
    confidence: float
    preference: Preference
    recommended_provider: str
    recommended_model: str
    rationale: str
    matched_signals: list[str]
    candidates: list[RouteCandidateItem]
    executed: bool
    completion: CompletionResponse | None = None
    # Optional debug/extension field reserved for future explainability payloads
    meta: dict[str, Any] | None = None
