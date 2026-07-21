"""
AI agent orchestration — sequential tool plans without LangChain.

Why this exists:
- Reuses classify / RAG / LLM services as tools behind one auditable runner.
- Fixed definition steps stay for governance demos.
- Free-form planner maps a natural-language goal → validated tool list → same runner.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.agent import AgentDefinition, AgentRun
from app.models.user import User
from app.schemas.agent import (
    AVAILABLE_TOOLS,
    AgentDefinitionCreate,
    AgentDefinitionResponse,
    AgentPlanPreviewResponse,
    AgentPlanRunRequest,
    AgentRunRequest,
    AgentRunResponse,
    AgentStepLogItem,
)
from app.schemas.rag import RagQueryRequest
from app.services.llm_service import run_completion
from app.services.organization_service import get_or_create_organization
from app.services.rag_service import query_rag, retrieve_chunks
from app.services.router_service import classify_only

logger = logging.getLogger("app.agents")

_FREEFORM_DEFINITION_NAME = "Free-form Planner"
_MAX_PLAN_STEPS = 8
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _def_to_response(row: AgentDefinition) -> AgentDefinitionResponse:
    return AgentDefinitionResponse(
        id=row.id,
        organization_id=row.organization_id,
        organization_slug=row.organization.slug,
        name=row.name,
        description=row.description,
        steps=list(row.steps or []),
        default_provider=row.default_provider,
        default_model=row.default_model,
        max_steps=row.max_steps,
        is_active=row.is_active,
        created_at=row.created_at,
    )


def _run_to_response(row: AgentRun) -> AgentRunResponse:
    steps: list[AgentStepLogItem] = []
    for item in row.steps_log or []:
        steps.append(AgentStepLogItem.model_validate(item))
    return AgentRunResponse(
        id=row.id,
        definition_id=row.definition_id,
        definition_name=row.definition.name,
        organization_slug=row.organization.slug,
        input_text=row.input_text,
        status=row.status,
        output_text=row.output_text,
        error_message=row.error_message,
        steps_log=steps,
        created_at=row.created_at,
    )


def ensure_default_agents(db: Session, *, organization_slug: str = "default") -> None:
    """Seed a Knowledge Assistant definition when the org has none."""
    org = get_or_create_organization(db, slug=organization_slug.strip().lower())
    existing = db.scalar(
        select(AgentDefinition.id).where(AgentDefinition.organization_id == org.id).limit(1)
    )
    if existing is not None:
        return
    db.add(
        AgentDefinition(
            organization_id=org.id,
            name="Knowledge Assistant",
            description=(
                "Classifies the request, searches the org knowledge base, "
                "then drafts a grounded answer."
            ),
            steps=["classify_task", "rag_search", "llm_answer"],
            default_provider="groq",
            default_model=None,
            max_steps=8,
            is_active=True,
        )
    )
    db.add(
        AgentDefinition(
            organization_id=org.id,
            name="RAG Specialist",
            description="Runs a full retrieval-augmented answer in one tool step.",
            steps=["rag_answer"],
            default_provider="groq",
            default_model=None,
            max_steps=4,
            is_active=True,
        )
    )
    db.commit()


def list_definitions(
    db: Session,
    *,
    organization_slug: str = "default",
) -> list[AgentDefinitionResponse]:
    ensure_default_agents(db, organization_slug=organization_slug)
    org = get_or_create_organization(db, slug=organization_slug.strip().lower())
    rows = db.scalars(
        select(AgentDefinition)
        .options(joinedload(AgentDefinition.organization))
        .where(AgentDefinition.organization_id == org.id)
        .order_by(AgentDefinition.created_at.asc())
    ).all()
    return [_def_to_response(row) for row in rows]


def create_definition(db: Session, body: AgentDefinitionCreate) -> AgentDefinitionResponse:
    unknown = [s for s in body.steps if s not in AVAILABLE_TOOLS]
    if unknown:
        raise ValidationAppError(
            f"Unknown tools: {unknown}. Available: {list(AVAILABLE_TOOLS)}"
        )
    org = get_or_create_organization(db, slug=body.organization_slug.strip().lower())
    row = AgentDefinition(
        organization_id=org.id,
        name=body.name.strip(),
        description=body.description.strip() if body.description else None,
        steps=body.steps,
        default_provider=body.default_provider.strip().lower(),
        default_model=body.default_model,
        max_steps=body.max_steps,
        is_active=True,
    )
    db.add(row)
    db.commit()
    loaded = db.scalar(
        select(AgentDefinition)
        .options(joinedload(AgentDefinition.organization))
        .where(AgentDefinition.id == row.id)
    )
    assert loaded is not None
    return _def_to_response(loaded)


def list_runs(
    db: Session,
    *,
    organization_slug: str = "default",
    limit: int = 20,
) -> list[AgentRunResponse]:
    org = get_or_create_organization(db, slug=organization_slug.strip().lower())
    rows = db.scalars(
        select(AgentRun)
        .options(
            joinedload(AgentRun.definition),
            joinedload(AgentRun.organization),
        )
        .where(AgentRun.organization_id == org.id)
        .order_by(AgentRun.created_at.desc())
        .limit(limit)
    ).all()
    return [_run_to_response(row) for row in rows]


def get_run(db: Session, run_id: UUID, *, organization_id: UUID) -> AgentRunResponse:
    row = db.scalar(
        select(AgentRun)
        .options(
            joinedload(AgentRun.definition),
            joinedload(AgentRun.organization),
        )
        .where(AgentRun.id == run_id)
    )
    if row is None or row.organization_id != organization_id:
        raise NotFoundError("Agent run not found")
    return _run_to_response(row)


def _normalize_tool_plan(tools: list[str], *, rationale: str) -> tuple[list[str], str]:
    """Validate, dedupe, cap, and ensure a terminal answer tool."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for tool in tools:
        name = str(tool).strip()
        if name in AVAILABLE_TOOLS and name not in seen:
            seen.add(name)
            cleaned.append(name)
        if len(cleaned) >= _MAX_PLAN_STEPS:
            break

    if not cleaned:
        cleaned = ["llm_answer"]
        rationale = "Fallback — llm_answer only (empty/invalid plan)."

    if "llm_answer" not in cleaned and "rag_answer" not in cleaned:
        cleaned.append("llm_answer")
        rationale += " Added llm_answer as terminal step."

    return cleaned, rationale


def plan_tools_heuristic(goal: str) -> tuple[list[str], str]:
    """
    Deterministic free-form planner (governance-friendly, no LLM cost).

    Returns (ordered tool names, human-readable rationale).
    """
    text = goal.strip().lower()
    if not text:
        raise ValidationAppError("goal must not be empty")

    knowledge_signals = (
        "knowledge",
        "document",
        "policy",
        "handbook",
        "rag",
        "cite",
        "according to",
        "from our",
        "in the docs",
        "kb",
        "wiki",
    )
    classify_signals = (
        "classify",
        "what kind",
        "task type",
        "categorize",
        "route",
    )
    answer_signals = (
        "answer",
        "explain",
        "summarize",
        "write",
        "draft",
        "how",
        "what",
        "why",
        "which",
    )

    wants_knowledge = any(s in text for s in knowledge_signals)
    wants_classify = any(s in text for s in classify_signals)
    wants_answer = any(s in text for s in answer_signals) or True

    if wants_knowledge and not wants_classify:
        plan = ["rag_answer"]
        rationale = (
            "Goal references org knowledge/docs — use rag_answer for grounded retrieval + answer."
        )
    elif wants_knowledge and wants_classify:
        plan = ["classify_task", "rag_search", "llm_answer"]
        rationale = (
            "Goal needs classification and knowledge — classify, retrieve chunks, then llm_answer."
        )
    elif wants_classify and not wants_knowledge:
        plan = ["classify_task", "llm_answer"]
        rationale = "Goal focuses on classification — classify_task then llm_answer."
    elif wants_answer:
        plan = ["classify_task", "llm_answer"]
        rationale = (
            "General goal — classify for routing context, then llm_answer "
            "(no knowledge keywords detected)."
        )
    else:
        plan = ["llm_answer"]
        rationale = "Minimal plan — direct llm_answer."

    return _normalize_tool_plan(plan, rationale=rationale)


def _provider_key_configured(provider: str) -> bool:
    settings = get_settings()
    key = provider.strip().lower()
    mapping = {
        "groq": settings.groq_api_key,
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "claude": settings.anthropic_api_key,
        "gemini": settings.google_api_key,
        "google": settings.google_api_key,
    }
    return bool(mapping.get(key))


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    fence = _JSON_FENCE_RE.search(raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
        return None


def _try_llm_plan(
    db: Session,
    *,
    goal: str,
    provider: str,
    model: str | None,
    organization_slug: str,
) -> tuple[list[str], str] | None:
    """Ask an LLM for a JSON tool plan; return None on any failure."""
    catalog = ", ".join(AVAILABLE_TOOLS)
    prompt = (
        "You are an enterprise AI agent planner. Choose an ordered tool plan for the goal.\n"
        f"Available tools (only these): {catalog}\n"
        "Rules:\n"
        "- Return ONLY valid JSON: {\"tools\": [\"...\"], \"rationale\": \"...\"}\n"
        "- 1 to 8 tools, no duplicates\n"
        "- End with llm_answer or rag_answer\n"
        "- Prefer rag_answer when the goal needs org knowledge/docs\n"
        "- Prefer classify_task when routing/classification matters\n"
        "- Prefer rag_search before llm_answer when retrieval + custom answer is needed\n\n"
        f"Goal: {goal}\n"
    )
    outcome = run_completion(
        db,
        provider=provider,
        prompt=prompt,
        model=model,
        organization_slug=organization_slug,
        temperature=0.1,
        max_tokens=256,
        raise_on_error=False,
        policy_prompt=goal,
    )
    if outcome.status != "success" or not outcome.response:
        logger.info(
            "LLM planner failed or empty: %s",
            outcome.error_message or outcome.status,
        )
        return None

    payload = _extract_json_object(outcome.response)
    if not payload:
        logger.info("LLM planner returned non-JSON response")
        return None

    tools_raw = payload.get("tools")
    if not isinstance(tools_raw, list):
        return None
    rationale = str(payload.get("rationale") or "LLM-selected tool plan.").strip()
    tools, rationale = _normalize_tool_plan(
        [str(t) for t in tools_raw],
        rationale=rationale,
    )
    return tools, rationale


def plan_tools_from_goal(
    goal: str,
    *,
    db: Session | None = None,
    provider: str | None = "groq",
    model: str | None = None,
    organization_slug: str = "default",
) -> tuple[list[str], str, str]:
    """
    Plan tools for a free-form goal.

    Returns (tools, rationale, planner_id) where planner_id is llm_v1 or heuristic_v1.
    """
    cleaned_goal = goal.strip()
    if not cleaned_goal:
        raise ValidationAppError("goal must not be empty")

    settings = get_settings()
    provider_key = (provider or "groq").strip().lower()

    if (
        settings.agents_use_llm_planner
        and db is not None
        and _provider_key_configured(provider_key)
    ):
        try:
            llm_plan = _try_llm_plan(
                db,
                goal=cleaned_goal,
                provider=provider_key,
                model=model,
                organization_slug=organization_slug,
            )
            if llm_plan is not None:
                tools, rationale = llm_plan
                return tools, rationale, "llm_v1"
        except Exception:  # noqa: BLE001
            logger.warning("LLM planner overlay raised; using heuristics", exc_info=True)

    tools, rationale = plan_tools_heuristic(cleaned_goal)
    return tools, rationale, "heuristic_v1"


def preview_plan(
    db: Session,
    body: AgentPlanRunRequest,
) -> AgentPlanPreviewResponse:
    tools, rationale, planner = plan_tools_from_goal(
        body.goal,
        db=db,
        provider=body.provider,
        model=body.model,
        organization_slug=body.organization_slug,
    )
    return AgentPlanPreviewResponse(
        goal=body.goal.strip(),
        tools=tools,
        rationale=rationale,
        planner=planner,
    )


def _get_or_create_freeform_definition(db: Session, *, organization_id: UUID) -> AgentDefinition:
    row = db.scalar(
        select(AgentDefinition)
        .where(
            AgentDefinition.organization_id == organization_id,
            AgentDefinition.name == _FREEFORM_DEFINITION_NAME,
        )
        .limit(1)
    )
    if row is not None:
        return row
    row = AgentDefinition(
        organization_id=organization_id,
        name=_FREEFORM_DEFINITION_NAME,
        description=(
            "System definition for free-form planner runs. "
            "Steps are replaced per request by the planner."
        ),
        steps=["llm_answer"],
        default_provider="groq",
        default_model=None,
        max_steps=_MAX_PLAN_STEPS,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _tool_classify(input_text: str) -> dict[str, Any]:
    result = classify_only(input_text)
    return {
        "task_type": result.task_type,
        "confidence": result.confidence,
        "matched_signals": result.matched_signals,
    }


def _tool_rag_search(db: Session, *, organization_id: UUID, question: str) -> dict[str, Any]:
    top, embedding_model = retrieve_chunks(
        db,
        organization_id=organization_id,
        question=question,
        top_k=4,
    )
    sources = [
        {
            "document_title": chunk.document.title,
            "chunk_index": chunk.chunk_index,
            "score": round(score, 4),
            "content": chunk.content[:500],
        }
        for chunk, score in top
    ]
    return {"embedding_model": embedding_model, "sources": sources}


def _tool_llm_answer(
    db: Session,
    *,
    organization_slug: str,
    input_text: str,
    provider: str,
    model: str | None,
    context: dict[str, Any],
) -> dict[str, Any]:
    sources = context.get("rag_sources") or []
    task_type = context.get("task_type")
    context_blocks = []
    for i, src in enumerate(sources, start=1):
        context_blocks.append(
            f"[{i}] {src.get('document_title')}: {src.get('content')}"
        )
    context_text = "\n".join(context_blocks) if context_blocks else "(no retrieved context)"
    prompt = (
        "You are an enterprise AI agent. Produce a clear final answer.\n"
        f"Detected task type: {task_type or 'unknown'}\n\n"
        f"Retrieved context:\n{context_text}\n\n"
        f"User request: {input_text}\n\n"
        "Answer:"
    )
    outcome = run_completion(
        db,
        provider=provider,
        prompt=prompt,
        model=model,
        organization_slug=organization_slug,
        temperature=0.3,
        max_tokens=256,
        raise_on_error=False,
        policy_prompt=input_text,
    )
    return {
        "answer": outcome.response or outcome.error_message or "",
        "status": outcome.status,
        "provider": outcome.provider,
        "model": outcome.model,
        "history_id": outcome.history_id,
        "error_message": outcome.error_message,
    }


def _tool_rag_answer(
    db: Session,
    *,
    organization_slug: str,
    input_text: str,
    provider: str,
    model: str | None,
) -> dict[str, Any]:
    result = query_rag(
        db,
        RagQueryRequest(
            question=input_text,
            top_k=4,
            provider=provider,
            model=model,
            max_tokens=256,
            organization_slug=organization_slug,
        ),
    )
    return {
        "answer": result.answer,
        "status": result.status,
        "provider": result.provider,
        "model": result.model,
        "history_id": result.history_id,
        "sources": [s.model_dump(mode="json") for s in result.sources],
        "error_message": result.error_message,
    }


def _execute_tool_plan(
    db: Session,
    *,
    run: AgentRun,
    plan: list[str],
    org_id: UUID,
    org_slug: str,
    input_text: str,
    provider: str,
    model: str | None,
    initial_steps_log: list[dict[str, Any]] | None = None,
) -> None:
    """Mutates `run` through success/error. Shared by fixed defs and free-form planner."""
    context: dict[str, Any] = {}
    steps_log: list[dict[str, Any]] = list(initial_steps_log or [])
    final_output: str | None = None
    start_idx = len(steps_log) + 1

    try:
        for offset, tool in enumerate(plan):
            idx = start_idx + offset
            if tool not in AVAILABLE_TOOLS:
                raise ValidationAppError(f"Unknown tool in plan: {tool}")

            if tool == "classify_task":
                detail = _tool_classify(input_text)
                context["task_type"] = detail.get("task_type")
                summary = f"Classified as {detail.get('task_type')} ({detail.get('confidence')})"
            elif tool == "rag_search":
                detail = _tool_rag_search(db, organization_id=org_id, question=input_text)
                context["rag_sources"] = detail.get("sources") or []
                summary = f"Retrieved {len(context['rag_sources'])} chunks"
            elif tool == "llm_answer":
                detail = _tool_llm_answer(
                    db,
                    organization_slug=org_slug,
                    input_text=input_text,
                    provider=provider,
                    model=model,
                    context=context,
                )
                final_output = detail.get("answer")
                summary = f"LLM answer via {detail.get('provider')}/{detail.get('model')}"
                if detail.get("status") != "success":
                    raise RuntimeError(detail.get("error_message") or "LLM step failed")
            elif tool == "rag_answer":
                detail = _tool_rag_answer(
                    db,
                    organization_slug=org_slug,
                    input_text=input_text,
                    provider=provider,
                    model=model,
                )
                final_output = detail.get("answer")
                context["rag_sources"] = detail.get("sources") or []
                summary = f"RAG answer via {detail.get('provider')}/{detail.get('model')}"
                if detail.get("status") != "success":
                    raise RuntimeError(detail.get("error_message") or "RAG step failed")
            else:
                raise ValidationAppError(f"Unhandled tool: {tool}")

            steps_log.append(
                {
                    "step": idx,
                    "tool": tool,
                    "status": "success",
                    "summary": summary,
                    "detail": detail,
                }
            )
            run.steps_log = list(steps_log)
            db.add(run)
            db.commit()

        run.status = "success"
        run.output_text = final_output or "Agent completed with no final answer step."
        run.steps_log = steps_log
        db.add(run)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        steps_log.append(
            {
                "step": len(steps_log) + 1,
                "tool": "runner",
                "status": "error",
                "summary": str(exc),
                "detail": None,
            }
        )
        run.status = "error"
        run.error_message = str(exc)
        run.steps_log = steps_log
        run.output_text = final_output
        db.add(run)
        db.commit()


def run_agent(
    db: Session,
    body: AgentRunRequest,
    *,
    actor: User | None = None,
) -> AgentRunResponse:
    org = get_or_create_organization(db, slug=body.organization_slug.strip().lower())
    definition = db.scalar(
        select(AgentDefinition)
        .options(joinedload(AgentDefinition.organization))
        .where(AgentDefinition.id == body.definition_id)
    )
    if definition is None or definition.organization_id != org.id:
        raise NotFoundError("Agent definition not found")
    if not definition.is_active:
        raise ValidationAppError("Agent definition is inactive")

    provider = (body.provider or definition.default_provider).strip().lower()
    model = body.model if body.model is not None else definition.default_model
    input_text = body.input_text.strip()
    if not input_text:
        raise ValidationAppError("input_text must not be empty")

    run = AgentRun(
        organization_id=org.id,
        definition_id=definition.id,
        actor_user_id=actor.id if actor else None,
        input_text=input_text,
        status="running",
        steps_log=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    plan = list(definition.steps or [])[: definition.max_steps]
    _execute_tool_plan(
        db,
        run=run,
        plan=plan,
        org_id=org.id,
        org_slug=org.slug,
        input_text=input_text,
        provider=provider,
        model=model,
    )

    loaded = db.scalar(
        select(AgentRun)
        .options(
            joinedload(AgentRun.definition),
            joinedload(AgentRun.organization),
        )
        .where(AgentRun.id == run.id)
    )
    assert loaded is not None
    return _run_to_response(loaded)


def run_planned_agent(
    db: Session,
    body: AgentPlanRunRequest,
    *,
    actor: User | None = None,
) -> AgentRunResponse:
    """Plan tools from a free-form goal, then execute via the shared runner."""
    org = get_or_create_organization(db, slug=body.organization_slug.strip().lower())
    goal = body.goal.strip()
    if not goal:
        raise ValidationAppError("goal must not be empty")

    tools, rationale, planner = plan_tools_from_goal(
        goal,
        db=db,
        provider=body.provider,
        model=body.model,
        organization_slug=body.organization_slug,
    )
    definition = _get_or_create_freeform_definition(db, organization_id=org.id)
    definition.steps = tools
    definition.default_provider = (body.provider or definition.default_provider).strip().lower()
    if body.model is not None:
        definition.default_model = body.model
    db.add(definition)
    db.commit()
    db.refresh(definition)

    provider = definition.default_provider
    model = definition.default_model

    run = AgentRun(
        organization_id=org.id,
        definition_id=definition.id,
        actor_user_id=actor.id if actor else None,
        input_text=goal,
        status="running",
        steps_log=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    planner_log = [
        {
            "step": 0,
            "tool": "plan_tools",
            "status": "success",
            "summary": rationale,
            "detail": {"tools": tools, "planner": planner},
        }
    ]
    _execute_tool_plan(
        db,
        run=run,
        plan=tools[: definition.max_steps],
        org_id=org.id,
        org_slug=org.slug,
        input_text=goal,
        provider=provider,
        model=model,
        initial_steps_log=planner_log,
    )

    loaded = db.scalar(
        select(AgentRun)
        .options(
            joinedload(AgentRun.definition),
            joinedload(AgentRun.organization),
        )
        .where(AgentRun.id == run.id)
    )
    assert loaded is not None
    return _run_to_response(loaded)
