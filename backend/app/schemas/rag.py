"""RAG request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RagIngestRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1, max_length=200_000)
    source: str | None = Field(default=None, max_length=255)
    organization_slug: str = Field(default="default", max_length=100)


class RagDocumentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    organization_slug: str
    title: str
    source: str | None
    chunk_count: int
    embedding_model: str
    content_preview: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RagSourceItem(BaseModel):
    document_id: UUID
    document_title: str
    chunk_id: UUID
    chunk_index: int
    score: float
    content: str


class RagQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=10)
    provider: str = Field(default="groq", max_length=50)
    model: str | None = None
    max_tokens: int = Field(default=512, ge=16, le=4096)
    organization_slug: str = Field(default="default", max_length=100)


class RagQueryResponse(BaseModel):
    answer: str
    provider: str
    model: str
    status: str
    error_message: str | None = None
    history_id: str | None = None
    sources: list[RagSourceItem]
    embedding_model: str
