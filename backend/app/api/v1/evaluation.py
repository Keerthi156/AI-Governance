"""
Evaluation HTTP routes (enhanced).
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.evaluation import EvaluationRun
from app.models.user import User
from app.schemas.evaluation import (
    CompareStrategiesBody,
    EvaluateArenaBody,
    EvaluationResponse,
    EvaluationScoreItem,
    StrategyComparisonResponse,
)
from app.services.evaluation_service import (
    compare_strategies,
    evaluate_arena_run,
    get_evaluation,
    list_evaluations_for_arena,
)

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


def _to_response(evaluation: EvaluationRun) -> EvaluationResponse:
    scores = sorted(evaluation.scores, key=lambda s: s.rank)
    return EvaluationResponse(
        id=evaluation.id,
        arena_run_id=evaluation.arena_run_id,
        strategy=evaluation.strategy,
        task_type=evaluation.task_type,
        metric_weights=evaluation.metric_weights,
        score_gap=evaluation.score_gap,
        recommended_history_id=evaluation.recommended_history_id,
        recommended_provider=evaluation.recommended_provider,
        recommended_model=evaluation.recommended_model,
        summary=evaluation.summary,
        scores=[
            EvaluationScoreItem(
                id=score.id,
                history_id=score.history_id,
                provider=score.provider,
                model=score.model,
                status=score.status,
                success_score=score.success_score,
                latency_score=score.latency_score,
                cost_score=score.cost_score,
                substance_score=score.substance_score,
                structure_score=getattr(score, "structure_score", None) or 0,
                relevance_score=getattr(score, "relevance_score", None) or 0,
                composite_score=score.composite_score,
                rank=score.rank,
                rationale=score.rationale,
            )
            for score in scores
        ],
        created_at=evaluation.created_at,
    )


@router.post("/arena", response_model=EvaluationResponse)
def create_arena_evaluation(
    body: EvaluateArenaBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("evaluation:run")),
) -> EvaluationResponse:
    """Evaluate an Arena run and recommend a model for the chosen strategy."""
    evaluation = evaluate_arena_run(
        db,
        arena_run_id=body.arena_run_id,
        strategy=body.strategy,
        task_type=body.task_type,
    )
    return _to_response(evaluation)


@router.post("/arena/compare", response_model=StrategyComparisonResponse)
def compare_arena_strategies(
    body: CompareStrategiesBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("evaluation:run")),
) -> StrategyComparisonResponse:
    """Run multiple strategies against one Arena run and return all scorecards."""
    evaluations = compare_strategies(
        db,
        arena_run_id=body.arena_run_id,
        task_type=body.task_type,
        strategies=body.strategies,
    )
    return StrategyComparisonResponse(
        arena_run_id=body.arena_run_id,
        evaluations=[_to_response(item) for item in evaluations],
    )


@router.get("/arena/{arena_run_id}", response_model=list[EvaluationResponse])
def list_arena_evaluations(
    arena_run_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("evaluation:read")),
) -> list[EvaluationResponse]:
    """List prior evaluations for an Arena run (newest first)."""
    rows = list_evaluations_for_arena(db, arena_run_id)
    return [_to_response(row) for row in rows]


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
def read_evaluation(
    evaluation_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("evaluation:read")),
) -> EvaluationResponse:
    """Fetch a persisted evaluation by id."""
    return _to_response(get_evaluation(db, evaluation_id))
