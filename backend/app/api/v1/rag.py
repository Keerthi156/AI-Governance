"""
Enterprise RAG HTTP routes.
"""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.rag import (
    RagDocumentResponse,
    RagIngestRequest,
    RagQueryRequest,
    RagQueryResponse,
)
from app.services.audit_service import record_event
from app.services.document_extract_service import extract_text_from_upload
from app.services.rag_service import (
    delete_document,
    ingest_document,
    list_documents,
    query_rag,
)

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/documents", response_model=list[RagDocumentResponse])
def get_documents(
    organization_slug: str = Query(default="default"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("rag:read")),
) -> list[RagDocumentResponse]:
    """List ingested knowledge documents for an organization."""
    return list_documents(db, organization_slug=organization_slug)


@router.post("/documents", response_model=RagDocumentResponse, status_code=201)
def post_document(
    body: RagIngestRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("rag:write")),
) -> RagDocumentResponse:
    """Ingest a document: chunk, embed, and store for retrieval."""
    created = ingest_document(db, body)
    record_event(
        action="rag.ingest",
        status="success",
        actor=current_user,
        resource_type="rag_document",
        resource_id=str(created.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Ingested “{created.title}” ({created.chunk_count} chunks)",
        details={
            "chunk_count": created.chunk_count,
            "embedding_model": created.embedding_model,
            "source": "manual",
        },
    )
    return created


@router.post("/documents/upload", response_model=RagDocumentResponse, status_code=201)
async def post_document_upload(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("rag:write")),
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    organization_slug: str = Form(default="default"),
) -> RagDocumentResponse:
    """Upload .txt / .md / .pdf / .docx, extract text, then ingest via the same pipeline."""
    raw = await file.read()
    filename = file.filename or "upload"
    text, ext = extract_text_from_upload(filename=filename, data=raw)
    resolved_title = (title or "").strip() or Path(filename).stem or "Uploaded document"
    created = ingest_document(
        db,
        RagIngestRequest(
            title=resolved_title[:255],
            content=text,
            source=f"upload:{filename}"[:255],
            organization_slug=organization_slug.strip().lower() or "default",
        ),
    )
    record_event(
        action="rag.ingest.upload",
        status="success",
        actor=current_user,
        resource_type="rag_document",
        resource_id=str(created.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Uploaded “{created.title}” ({ext}, {created.chunk_count} chunks)",
        details={
            "chunk_count": created.chunk_count,
            "embedding_model": created.embedding_model,
            "filename": filename,
            "extension": ext,
        },
    )
    return created


@router.delete("/documents/{document_id}", status_code=204)
def remove_document(
    document_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("rag:write")),
) -> None:
    """Delete a knowledge document and its chunks."""
    delete_document(db, document_id, organization_id=current_user.organization_id)
    record_event(
        action="rag.delete",
        status="success",
        actor=current_user,
        resource_type="rag_document",
        resource_id=str(document_id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Deleted RAG document {document_id}",
    )


@router.post("/query", response_model=RagQueryResponse)
def post_query(
    body: RagQueryRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("rag:query")),
) -> RagQueryResponse:
    """Retrieve relevant chunks and generate a grounded answer."""
    result = query_rag(db, body)
    record_event(
        action="rag.query",
        status="success" if result.status == "success" else "failure",
        actor=current_user,
        resource_type="rag_query",
        resource_id=result.history_id,
        request_id=getattr(request.state, "request_id", None),
        summary=f"RAG query via {result.provider}/{result.model}",
        details={
            "source_count": len(result.sources),
            "embedding_model": result.embedding_model,
            "status": result.status,
        },
    )
    return result
