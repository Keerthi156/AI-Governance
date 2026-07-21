"""
AI agent HTTP routes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.agent import (
    AVAILABLE_TOOLS,
    AgentDefinitionCreate,
    AgentDefinitionResponse,
    AgentPlanPreviewResponse,
    AgentPlanRunRequest,
    AgentRunRequest,
    AgentRunResponse,
    AgentToolCatalogResponse,
)
from app.services.agent_service import (
    create_definition,
    get_run,
    list_definitions,
    list_runs,
    preview_plan,
    run_agent,
    run_planned_agent,
)
from app.services.audit_service import record_event

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/tools", response_model=AgentToolCatalogResponse)
def get_tools(
    _: User = Depends(require_permission("agents:read")),
) -> AgentToolCatalogResponse:
    """List available agent tools."""
    return AgentToolCatalogResponse(tools=list(AVAILABLE_TOOLS))


@router.get("/definitions", response_model=list[AgentDefinitionResponse])
def get_definitions(
    organization_slug: str = Query(default="default"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("agents:read")),
) -> list[AgentDefinitionResponse]:
    """List agent definitions (seeds defaults when empty)."""
    return list_definitions(db, organization_slug=organization_slug)


@router.post("/definitions", response_model=AgentDefinitionResponse, status_code=201)
def post_definition(
    body: AgentDefinitionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("agents:manage")),
) -> AgentDefinitionResponse:
    """Create a custom agent definition."""
    created = create_definition(db, body)
    record_event(
        action="agents.definition.create",
        status="success",
        actor=current_user,
        resource_type="agent_definition",
        resource_id=str(created.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Created agent “{created.name}”",
        details={"steps": created.steps},
    )
    return created


@router.get("/runs", response_model=list[AgentRunResponse])
def get_runs(
    organization_slug: str = Query(default="default"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("agents:read")),
) -> list[AgentRunResponse]:
    """List recent agent runs for an organization."""
    return list_runs(db, organization_slug=organization_slug, limit=limit)


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
def get_run_detail(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("agents:read")),
) -> AgentRunResponse:
    """Fetch one agent run."""
    return get_run(db, run_id, organization_id=current_user.organization_id)


@router.post("/plan", response_model=AgentPlanPreviewResponse)
def post_plan_preview(
    body: AgentPlanRunRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("agents:read")),
) -> AgentPlanPreviewResponse:
    """Preview which tools the free-form planner would choose (no execution)."""
    return preview_plan(db, body)


@router.post("/runs/plan", response_model=AgentRunResponse, status_code=201)
def post_planned_run(
    body: AgentPlanRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("agents:run")),
) -> AgentRunResponse:
    """Plan tools from a free-form goal, then execute the plan."""
    result = run_planned_agent(db, body, actor=current_user)
    record_event(
        action="agents.run.plan",
        status="success" if result.status == "success" else "failure",
        actor=current_user,
        resource_type="agent_run",
        resource_id=str(result.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Free-form planner run → {result.status}",
        details={
            "definition_id": str(result.definition_id),
            "steps": len(result.steps_log),
            "status": result.status,
            "planner": next(
                (
                    (s.detail or {}).get("planner")
                    for s in result.steps_log
                    if s.tool == "plan_tools"
                ),
                None,
            ),
        },
    )
    return result


@router.post("/runs", response_model=AgentRunResponse, status_code=201)
def post_run(
    body: AgentRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("agents:run")),
) -> AgentRunResponse:
    """Execute an agent definition against an input."""
    result = run_agent(db, body, actor=current_user)
    record_event(
        action="agents.run",
        status="success" if result.status == "success" else "failure",
        actor=current_user,
        resource_type="agent_run",
        resource_id=str(result.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Agent run {result.definition_name} → {result.status}",
        details={
            "definition_id": str(result.definition_id),
            "steps": len(result.steps_log),
            "status": result.status,
        },
    )
    return result
