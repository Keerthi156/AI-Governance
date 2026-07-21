"""
LLM HTTP routes.

Why this exists:
- Exposes a provider-agnostic completions endpoint for the playground UI.
- Streaming SSE route for token-by-token playground UX (Arena/RAG stay sync).
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.llm import CompletionRequest, CompletionResponse
from app.services.audit_service import record_event
from app.services.llm_service import run_completion, run_completion_stream

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/completions", response_model=CompletionResponse)
def create_completion(
    body: CompletionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("llm:run")),
) -> CompletionResponse:
    """Run a single-model LLM completion and persist prompt history."""
    outcome = run_completion(
        db,
        provider=body.provider,
        prompt=body.prompt,
        model=body.model,
        organization_slug=body.organization_slug,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    record_event(
        action="llm.completion",
        status="success" if outcome.status == "success" else "failure",
        actor=current_user,
        resource_type="prompt_history",
        resource_id=outcome.history_id,
        request_id=getattr(request.state, "request_id", None),
        summary=f"{outcome.provider}/{outcome.model} → {outcome.status}",
        details={
            "provider": outcome.provider,
            "model": outcome.model,
            "status": outcome.status,
            "total_tokens": outcome.total_tokens,
            "latency_ms": outcome.latency_ms,
        },
    )
    return CompletionResponse(
        history_id=outcome.history_id,
        provider=outcome.provider,
        model=outcome.model,
        prompt=outcome.prompt,
        response=outcome.response,
        status=outcome.status,
        error_message=outcome.error_message,
        prompt_tokens=outcome.prompt_tokens,
        completion_tokens=outcome.completion_tokens,
        total_tokens=outcome.total_tokens,
        estimated_cost_usd=outcome.estimated_cost_usd,
        latency_ms=outcome.latency_ms,
        organization_slug=outcome.organization_slug,
        arena_run_id=outcome.arena_run_id,
    )


@router.post("/completions/stream")
def create_completion_stream(
    body: CompletionRequest,
    request: Request,
    current_user: User = Depends(require_permission("llm:run")),
) -> StreamingResponse:
    """SSE stream of playground tokens (meta → token* → done|error)."""
    request_id = getattr(request.state, "request_id", None)
    actor_email = current_user.email
    organization_id = current_user.organization_id

    def event_generator() -> Iterator[str]:
        db = SessionLocal()
        final_status = "failure"
        history_id: str | None = None
        provider = body.provider
        model = body.model or ""
        try:
            for event in run_completion_stream(
                db,
                provider=body.provider,
                prompt=body.prompt,
                model=body.model,
                organization_slug=body.organization_slug,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            ):
                if event.get("type") == "meta":
                    history_id = event.get("history_id")
                    provider = event.get("provider") or provider
                    model = event.get("model") or model
                elif event.get("type") == "done":
                    final_status = "success"
                    history_id = event.get("history_id") or history_id
                    provider = event.get("provider") or provider
                    model = event.get("model") or model
                elif event.get("type") == "error":
                    history_id = event.get("history_id") or history_id
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            record_event(
                action="llm.completion.stream",
                status=final_status,
                organization_id=organization_id,
                actor_email=actor_email,
                resource_type="prompt_history",
                resource_id=history_id,
                request_id=request_id,
                summary=f"{provider}/{model} stream → {final_status}",
                details={
                    "provider": provider,
                    "model": model,
                    "status": final_status,
                    "stream": True,
                },
            )
            db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
