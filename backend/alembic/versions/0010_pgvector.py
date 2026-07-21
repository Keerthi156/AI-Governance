"""
Add pgvector extension and embedding_vec column for RAG ANN search.

Revision ID: 0010_pgvector
Revises: 0009_agents
Create Date: 2026-07-20

Notes:
- vector(384) matches local-hash-v1 (default offline embeddings).
- OpenAI 1536-d embeddings stay in JSONB; retrieval falls back to Python cosine.
- Requires a Postgres build with pgvector (docker: pgvector/pgvector:pg16).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_pgvector"
down_revision: Union[str, None] = "0009_agents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Use raw SQL so we do not require the pgvector Python package at migrate time.
    op.execute(
        "ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector(384)"
    )

    # Backfill local-hash (384-d) vectors from JSONB.
    op.execute(
        """
        UPDATE rag_chunks
        SET embedding_vec = embedding::text::vector
        WHERE embedding_vec IS NULL
          AND jsonb_typeof(embedding) = 'array'
          AND jsonb_array_length(embedding) = 384
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding_vec_hnsw
        ON rag_chunks
        USING hnsw (embedding_vec vector_cosine_ops)
        WHERE embedding_vec IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_embedding_vec_hnsw")
    op.execute("ALTER TABLE rag_chunks DROP COLUMN IF EXISTS embedding_vec")
    # Leave the extension installed — other DBs may depend on it.
