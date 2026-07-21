"""
Intelligent Task Router HTTP routes.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.llm import CompletionResponse
from app.schemas.router import (
    ClassifyRequest,
    ClassifyResponse,
    RouteCandidateItem,
    RouteRequest,
    RouteResponse,
)
from app.services.audit_service import record_event
from app.services.router_service import classify_only, route_prompt

router = APIRouter(prefix="/router", tags=["router"])


@router.post("/classify", response_model=ClassifyResponse)
def classify_task(
    body: ClassifyRequest,
    _: User = Depends(require_permission("router:classify")),
) -> ClassifyResponse:
    """Classify a prompt into a task type (no model call, no DB write)."""
    result = classify_only(body.prompt)
    return ClassifyResponse(
        task_type=result.task_type,  # type: ignore[arg-type]
        confidence=result.confidence,
        matched_signals=result.matched_signals,
        scores=result.scores,
    )


@router.post("/route", response_model=RouteResponse)
def route_task(
    body: RouteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("router:route")),
) -> RouteResponse:
    """
    Classify prompt, recommend provider/model, optionally execute completion.
    Persists a routing_decisions audit row.
    """
    outcome = route_prompt(
        db,
        prompt=body.prompt,
        preference=body.preference,
        organization_slug=body.organization_slug,
        execute=body.execute,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )

    completion_payload: CompletionResponse | None = None
    if outcome.completion is not None:
        c = outcome.completion
        completion_payload = CompletionResponse(
            history_id=c.history_id,
            provider=c.provider,
            model=c.model,
            prompt=c.prompt,
            response=c.response,
            status=c.status,
            error_message=c.error_message,
            prompt_tokens=c.prompt_tokens,
            completion_tokens=c.completion_tokens,
            total_tokens=c.total_tokens,
            estimated_cost_usd=c.estimated_cost_usd,
            latency_ms=c.latency_ms,
            organization_slug=c.organization_slug,
            arena_run_id=c.arena_run_id,
        )

    record_event(
        action="router.route",
        status="success",
        actor=current_user,
        resource_type="routing_decision",
        resource_id=str(outcome.decision_id) if outcome.decision_id else None,
        request_id=getattr(request.state, "request_id", None),
        summary=(
            f"Routed as {outcome.task_type} → "
            f"{outcome.recommended_provider}/{outcome.recommended_model}"
        ),
        details={
            "task_type": outcome.task_type,
            "preference": outcome.preference,
            "executed": outcome.executed,
            "recommended_provider": outcome.recommended_provider,
            "recommended_model": outcome.recommended_model,
        },
    )

    return RouteResponse(
        decision_id=outcome.decision_id,
        task_type=outcome.task_type,  # type: ignore[arg-type]
        preference=outcome.preference,  # type: ignore[arg-type]
        confidence=outcome.confidence,
        recommended_provider=outcome.recommended_provider,
        recommended_model=outcome.recommended_model,
        rationale=outcome.rationale,
        matched_signals=outcome.matched_signals,
        candidates=[
            RouteCandidateItem(
                provider=c.provider,
                model=c.model,
                score=c.score,
                available=c.available,
                reason=c.reason,
            )
            for c in outcome.candidates
        ],
        executed=outcome.executed,
        completion=completion_payload,
    )
