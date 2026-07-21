"""
Arena Mode HTTP routes.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.arena import ArenaRunRequest, ArenaRunResponse
from app.schemas.llm import CompletionResponse
from app.services.arena_service import ArenaParticipant, run_arena
from app.services.audit_service import record_event

router = APIRouter(prefix="/arena", tags=["arena"])


@router.post("/runs", response_model=ArenaRunResponse)
def create_arena_run(
    body: ArenaRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("arena:run")),
) -> ArenaRunResponse:
    """Compare one prompt across multiple provider/model participants."""
    outcome = run_arena(
        db,
        prompt=body.prompt,
        participants=[
            ArenaParticipant(provider=p.provider, model=p.model)
            for p in body.participants
        ],
        organization_slug=body.organization_slug,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    record_event(
        action="arena.run",
        status="success",
        actor=current_user,
        resource_type="arena_run",
        resource_id=outcome.arena_run_id,
        request_id=getattr(request.state, "request_id", None),
        summary=(
            f"Arena run with {len(outcome.results)} participants "
            f"({outcome.success_count} ok / {outcome.error_count} err)"
        ),
        details={
            "success_count": outcome.success_count,
            "error_count": outcome.error_count,
        },
    )

    return ArenaRunResponse(
        arena_run_id=outcome.arena_run_id,
        prompt=outcome.prompt,
        organization_slug=outcome.organization_slug,
        results=[
            CompletionResponse(
                history_id=item.history_id,
                provider=item.provider,
                model=item.model,
                prompt=item.prompt,
                response=item.response,
                status=item.status,
                error_message=item.error_message,
                prompt_tokens=item.prompt_tokens,
                completion_tokens=item.completion_tokens,
                total_tokens=item.total_tokens,
                estimated_cost_usd=item.estimated_cost_usd,
                latency_ms=item.latency_ms,
                organization_slug=item.organization_slug,
                arena_run_id=item.arena_run_id,
            )
            for item in outcome.results
        ],
        total_estimated_cost_usd=outcome.total_estimated_cost_usd,
        success_count=outcome.success_count,
        error_count=outcome.error_count,
    )
