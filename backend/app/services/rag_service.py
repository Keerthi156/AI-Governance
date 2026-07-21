"""
Enterprise RAG service — ingest, retrieve, and answer with citations.

Retrieval prefers pgvector cosine ANN for 384-d local-hash embeddings when
the extension is available; otherwise falls back to in-Python cosine over JSONB.
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.rag import RagChunk, RagDocument
from app.schemas.rag import (
    RagDocumentResponse,
    RagIngestRequest,
    RagQueryRequest,
    RagQueryResponse,
    RagSourceItem,
)
from app.services.embedding_service import LOCAL_DIM, cosine_similarity, embed_texts
from app.services.llm_service import run_completion
from app.services.organization_service import get_or_create_organization

logger = logging.getLogger("app.rag")

_CHUNK_SIZE = 700
_CHUNK_OVERLAP = 100


def _chunk_text(text: str) -> list[str]:
    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    if not cleaned:
        return []
    # Prefer paragraph splits, then window.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    units = paragraphs if paragraphs else [cleaned]
    chunks: list[str] = []
    for unit in units:
        if len(unit) <= _CHUNK_SIZE:
            chunks.append(unit)
            continue
        start = 0
        while start < len(unit):
            end = min(len(unit), start + _CHUNK_SIZE)
            chunks.append(unit[start:end].strip())
            if end >= len(unit):
                break
            start = max(end - _CHUNK_OVERLAP, start + 1)
    return [c for c in chunks if c]


def _doc_to_response(doc: RagDocument) -> RagDocumentResponse:
    preview = doc.content[:240] + ("…" if len(doc.content) > 240 else "")
    return RagDocumentResponse(
        id=doc.id,
        organization_id=doc.organization_id,
        organization_slug=doc.organization.slug,
        title=doc.title,
        source=doc.source,
        chunk_count=doc.chunk_count,
        embedding_model=doc.embedding_model,
        content_preview=preview,
        created_at=doc.created_at,
    )


def _pgvector_ready(db: Session) -> bool:
    """True when the vector extension exists (migration 0010 applied on a pgvector image)."""
    try:
        row = db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector' LIMIT 1")
        ).first()
        return row is not None
    except Exception:  # noqa: BLE001
        logger.debug("pgvector readiness check failed", exc_info=True)
        db.rollback()
        return False


def list_documents(
    db: Session,
    *,
    organization_slug: str = "default",
) -> list[RagDocumentResponse]:
    org = get_or_create_organization(db, slug=organization_slug.strip().lower())
    rows = db.scalars(
        select(RagDocument)
        .options(joinedload(RagDocument.organization))
        .where(RagDocument.organization_id == org.id)
        .order_by(RagDocument.created_at.desc())
    ).all()
    return [_doc_to_response(row) for row in rows]


def ingest_document(db: Session, body: RagIngestRequest) -> RagDocumentResponse:
    content = body.content.strip()
    if not content:
        raise ValidationAppError("Document content must not be empty")

    chunks = _chunk_text(content)
    if not chunks:
        raise ValidationAppError("Document produced no chunks")

    org = get_or_create_organization(db, slug=body.organization_slug.strip().lower())
    vectors, embedding_model = embed_texts(chunks)

    doc = RagDocument(
        organization_id=org.id,
        title=body.title.strip(),
        source=body.source.strip() if body.source else None,
        content=content,
        chunk_count=len(chunks),
        embedding_model=embedding_model,
    )
    db.add(doc)
    db.flush()

    for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors, strict=True)):
        # Dual-write: JSONB always; pgvector column only for LOCAL_DIM vectors.
        embedding_vec = vector if len(vector) == LOCAL_DIM else None
        db.add(
            RagChunk(
                document_id=doc.id,
                organization_id=org.id,
                chunk_index=idx,
                content=chunk_text,
                token_estimate=max(1, len(chunk_text.split())),
                embedding=vector,
                embedding_vec=embedding_vec,
            )
        )
    db.commit()
    loaded = db.scalar(
        select(RagDocument)
        .options(joinedload(RagDocument.organization))
        .where(RagDocument.id == doc.id)
    )
    assert loaded is not None
    return _doc_to_response(loaded)


def delete_document(db: Session, document_id: UUID, *, organization_id: UUID) -> None:
    doc = db.scalar(select(RagDocument).where(RagDocument.id == document_id))
    if doc is None or doc.organization_id != organization_id:
        raise NotFoundError("Document not found")
    db.delete(doc)
    db.commit()


def _retrieve_chunks_python(
    db: Session,
    *,
    organization_id: UUID,
    query_vec: list[float],
    top_k: int,
) -> list[tuple[RagChunk, float]]:
    rows = db.scalars(
        select(RagChunk)
        .options(joinedload(RagChunk.document))
        .where(RagChunk.organization_id == organization_id)
    ).all()

    scored: list[tuple[RagChunk, float]] = []
    for row in rows:
        emb = row.embedding or []
        if len(emb) != len(query_vec):
            continue
        score = cosine_similarity(query_vec, emb)
        scored.append((row, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_k]


def _retrieve_chunks_pgvector(
    db: Session,
    *,
    organization_id: UUID,
    query_vec: list[float],
    top_k: int,
) -> list[tuple[RagChunk, float]]:
    """ANN via pgvector cosine distance; similarity = 1 - distance for L2-normalized vectors."""
    distance = RagChunk.embedding_vec.cosine_distance(query_vec)
    score_expr = (1 - distance).label("score")
    rows = db.execute(
        select(RagChunk, score_expr)
        .options(joinedload(RagChunk.document))
        .where(
            RagChunk.organization_id == organization_id,
            RagChunk.embedding_vec.is_not(None),
        )
        .order_by(distance)
        .limit(top_k)
    ).all()
    return [(chunk, float(score)) for chunk, score in rows]


def retrieve_chunks(
    db: Session,
    *,
    organization_id: UUID,
    question: str,
    top_k: int = 4,
) -> tuple[list[tuple[RagChunk, float]], str]:
    """Return top-k (chunk, score) pairs and the query embedding model used."""
    q_vectors, embedding_model = embed_texts([question])
    query_vec = q_vectors[0]
    settings = get_settings()

    use_pgvector = (
        settings.rag_use_pgvector
        and len(query_vec) == LOCAL_DIM
        and _pgvector_ready(db)
    )

    if use_pgvector:
        try:
            return _retrieve_chunks_pgvector(
                db,
                organization_id=organization_id,
                query_vec=query_vec,
                top_k=top_k,
            ), embedding_model
        except Exception:  # noqa: BLE001
            logger.warning(
                "pgvector retrieve failed; falling back to Python cosine",
                exc_info=True,
            )
            db.rollback()

    return (
        _retrieve_chunks_python(
            db,
            organization_id=organization_id,
            query_vec=query_vec,
            top_k=top_k,
        ),
        embedding_model,
    )


def query_rag(db: Session, body: RagQueryRequest) -> RagQueryResponse:
    org = get_or_create_organization(db, slug=body.organization_slug.strip().lower())
    question = body.question.strip()
    if not question:
        raise ValidationAppError("Question must not be empty")

    top, embedding_model = retrieve_chunks(
        db,
        organization_id=org.id,
        question=question,
        top_k=body.top_k,
    )

    sources = [
        RagSourceItem(
            document_id=chunk.document_id,
            document_title=chunk.document.title,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            score=round(score, 4),
            content=chunk.content,
        )
        for chunk, score in top
    ]

    if not sources:
        return RagQueryResponse(
            answer=(
                "No knowledge documents are available for this organization yet. "
                "Ingest a document first, then ask again."
            ),
            provider=body.provider,
            model=body.model or "n/a",
            status="success",
            sources=[],
            embedding_model=embedding_model,
        )

    context_blocks = []
    for i, src in enumerate(sources, start=1):
        context_blocks.append(
            f"[{i}] Title: {src.document_title}\n{src.content}"
        )
    context = "\n\n".join(context_blocks)

    prompt = (
        "You are an enterprise assistant. Answer the question using ONLY the "
        "provided context. If the context is insufficient, say you do not know.\n"
        "Cite sources using [n] markers when relevant.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

    outcome = run_completion(
        db,
        provider=body.provider,
        prompt=prompt,
        model=body.model,
        organization_slug=org.slug,
        temperature=0.2,
        max_tokens=body.max_tokens,
        raise_on_error=False,
        # Governance scans the user question; retrieved context may legitimately
        # discuss blocked terms (e.g. policy text about passwords).
        policy_prompt=question,
    )

    return RagQueryResponse(
        answer=outcome.response
        or outcome.error_message
        or "No answer generated.",
        provider=outcome.provider,
        model=outcome.model,
        status=outcome.status,
        error_message=outcome.error_message,
        history_id=outcome.history_id,
        sources=sources,
        embedding_model=embedding_model,
    )
