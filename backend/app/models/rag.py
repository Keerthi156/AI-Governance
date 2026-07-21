"""
RAG document and chunk models.

Why this exists:
- Enterprise RAG needs durable, org-scoped knowledge separate from prompt history.
- JSONB embeddings remain for portability / OpenAI 1536-d vectors.
- embedding_vec (pgvector, 384-d) enables SQL ANN for the default local-hash path.
"""

from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Must match embedding_service.LOCAL_DIM (local-hash-v1).
_PGVECTOR_DIM = 384


class RagDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A knowledge document ingested for retrieval-augmented generation."""

    __tablename__ = "rag_documents"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)

    organization = relationship("Organization", back_populates="rag_documents")
    chunks = relationship(
        "RagChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="RagChunk.chunk_index",
    )

    def __repr__(self) -> str:
        return f"<RagDocument title={self.title!r} chunks={self.chunk_count}>"


class RagChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A chunk of a document with an embedding vector for similarity search."""

    __tablename__ = "rag_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("rag_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    embedding: Mapped[list] = mapped_column(JSONB, nullable=False)
    # pgvector ANN column — populated for LOCAL_DIM (384) embeddings only.
    embedding_vec: Mapped[list | None] = mapped_column(
        Vector(_PGVECTOR_DIM),
        nullable=True,
    )

    document = relationship("RagDocument", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<RagChunk doc={self.document_id} idx={self.chunk_index}>"
