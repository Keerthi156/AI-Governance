"""
Enhanced evaluation engine — score Arena participants and recommend a model.

Extends v1 heuristics with structure/relevance metrics, task-aware weights,
strategy comparison, and list-by-arena APIs.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.evaluation import EvaluationRun, EvaluationScore
from app.models.prompt_history import PromptHistory
from app.services.evaluation_metrics import (
    STRATEGIES,
    normalize_inverse,
    relevance_score,
    resolve_weights,
    structure_score,
    substance_score,
)


def evaluate_arena_run(
    db: Session,
    *,
    arena_run_id: UUID,
    strategy: str = "balanced",
    task_type: str | None = None,
) -> EvaluationRun:
    """Score all participants in an Arena run and persist the evaluation."""
    strategy_key = strategy.strip().lower()
    if strategy_key not in STRATEGIES:
        raise ValidationAppError(
            f"Unsupported strategy '{strategy}'. Supported: {sorted(STRATEGIES)}",
        )

    try:
        weights = resolve_weights(strategy_key, task_type)
    except KeyError as exc:
        raise ValidationAppError(f"Unsupported strategy '{strategy}'") from exc

    rows = db.scalars(
        select(PromptHistory)
        .where(PromptHistory.arena_run_id == arena_run_id)
        .order_by(PromptHistory.created_at.asc())
    ).all()
    if not rows:
        raise NotFoundError(f"Arena run '{arena_run_id}' not found")

    latencies = [
        Decimal(row.latency_ms) if row.latency_ms is not None else None for row in rows
    ]
    costs = [
        Decimal(row.estimated_cost_usd) if row.estimated_cost_usd is not None else None
        for row in rows
    ]
    latency_scores = normalize_inverse(latencies)
    cost_scores = normalize_inverse(costs)

    scored: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        success = Decimal("1") if row.status == "success" else Decimal("0")
        substance = substance_score(row.status, row.response)
        structure = structure_score(row.status, row.response)
        relevance = relevance_score(row.status, row.prompt, row.response)

        composite = (
            success * weights["success"]
            + latency_scores[idx] * weights["latency"]
            + cost_scores[idx] * weights["cost"]
            + substance * weights["substance"]
            + structure * weights["structure"]
            + relevance * weights["relevance"]
        ).quantize(Decimal("0.0001"))

        rationale_parts = [
            f"success={success}",
            f"latency={latency_scores[idx]:.4f}",
            f"cost={cost_scores[idx]:.4f}",
            f"substance={substance}",
            f"structure={structure}",
            f"relevance={relevance}",
        ]
        if row.status != "success":
            rationale_parts.append(f"error={row.error_message or 'failed'}")

        scored.append(
            {
                "row": row,
                "success": success,
                "latency": latency_scores[idx].quantize(Decimal("0.0001")),
                "cost": cost_scores[idx].quantize(Decimal("0.0001")),
                "substance": substance,
                "structure": structure,
                "relevance": relevance,
                "composite": composite,
                "rationale": "; ".join(rationale_parts),
            }
        )

    scored.sort(key=lambda item: item["composite"], reverse=True)
    for rank, item in enumerate(scored, start=1):
        item["rank"] = rank

    winner = scored[0]
    runner_up = scored[1] if len(scored) > 1 else None
    score_gap = None
    if runner_up is not None:
        score_gap = (winner["composite"] - runner_up["composite"]).quantize(
            Decimal("0.0001")
        )

    winner_row: PromptHistory = winner["row"]
    task_label = (task_type or "general").lower()
    if winner_row.status != "success":
        summary = (
            f"Strategy '{strategy_key}' (task={task_label}): no successful participants. "
            f"Top ranked (still failed): {winner_row.provider}/{winner_row.model}."
        )
        recommended_history_id = None
        recommended_provider = None
        recommended_model = None
    else:
        gap_txt = f" gap={score_gap}" if score_gap is not None else ""
        summary = (
            f"Strategy '{strategy_key}' (task={task_label}) recommends "
            f"{winner_row.provider}/{winner_row.model} "
            f"(score={winner['composite']}{gap_txt})."
        )
        recommended_history_id = winner_row.id
        recommended_provider = winner_row.provider
        recommended_model = winner_row.model

    evaluation = EvaluationRun(
        arena_run_id=arena_run_id,
        strategy=strategy_key,
        task_type=task_label,
        metric_weights={k: str(v) for k, v in weights.items()},
        score_gap=score_gap,
        recommended_history_id=recommended_history_id,
        recommended_provider=recommended_provider,
        recommended_model=recommended_model,
        summary=summary,
    )
    db.add(evaluation)
    db.flush()

    for item in scored:
        row = item["row"]
        db.add(
            EvaluationScore(
                evaluation_run_id=evaluation.id,
                history_id=row.id,
                provider=row.provider,
                model=row.model,
                status=row.status,
                success_score=item["success"],
                latency_score=item["latency"],
                cost_score=item["cost"],
                substance_score=item["substance"],
                structure_score=item["structure"],
                relevance_score=item["relevance"],
                composite_score=item["composite"],
                rank=item["rank"],
                rationale=item["rationale"],
            )
        )

    db.commit()
    db.refresh(evaluation)
    return db.scalar(
        select(EvaluationRun)
        .options(joinedload(EvaluationRun.scores))
        .where(EvaluationRun.id == evaluation.id)
    )


def get_evaluation(db: Session, evaluation_id: UUID) -> EvaluationRun:
    evaluation = db.scalar(
        select(EvaluationRun)
        .options(joinedload(EvaluationRun.scores))
        .where(EvaluationRun.id == evaluation_id)
    )
    if evaluation is None:
        raise NotFoundError(f"Evaluation '{evaluation_id}' not found")
    return evaluation


def list_evaluations_for_arena(
    db: Session,
    arena_run_id: UUID,
) -> list[EvaluationRun]:
    rows = db.scalars(
        select(EvaluationRun)
        .options(joinedload(EvaluationRun.scores))
        .where(EvaluationRun.arena_run_id == arena_run_id)
        .order_by(EvaluationRun.created_at.desc())
    ).unique().all()
    return list(rows)


def compare_strategies(
    db: Session,
    *,
    arena_run_id: UUID,
    task_type: str | None = None,
    strategies: list[str] | None = None,
) -> list[EvaluationRun]:
    """
    Run multiple strategies against the same arena run and persist each.
    """
    selected = strategies or list(STRATEGIES.keys())
    unknown = [s for s in selected if s not in STRATEGIES]
    if unknown:
        raise ValidationAppError(
            f"Unsupported strategies: {unknown}. Supported: {sorted(STRATEGIES)}"
        )

    # Ensure arena exists before writing many rows.
    exists = db.scalar(
        select(PromptHistory.id).where(PromptHistory.arena_run_id == arena_run_id).limit(1)
    )
    if exists is None:
        raise NotFoundError(f"Arena run '{arena_run_id}' not found")

    results: list[EvaluationRun] = []
    for strategy in selected:
        results.append(
            evaluate_arena_run(
                db,
                arena_run_id=arena_run_id,
                strategy=strategy,
                task_type=task_type,
            )
        )
    return results
