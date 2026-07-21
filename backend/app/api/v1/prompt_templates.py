"""
Prompt template HTTP routes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.prompt_template import PromptTemplateCreate, PromptTemplateResponse
from app.services.audit_service import record_event
from app.services.prompt_template_service import (
    create_template,
    delete_template,
    list_templates,
)

router = APIRouter(prefix="/prompt-templates", tags=["prompt-templates"])


@router.get("", response_model=list[PromptTemplateResponse])
def get_templates(
    organization_slug: str = Query(default="default"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("templates:read")),
) -> list[PromptTemplateResponse]:
    """List org prompt templates (seeds defaults when empty)."""
    return list_templates(db, organization_slug=organization_slug)


@router.post("", response_model=PromptTemplateResponse, status_code=201)
def post_template(
    body: PromptTemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("templates:write")),
) -> PromptTemplateResponse:
    """Save a new prompt template for the organization."""
    created = create_template(db, body, actor=current_user)
    record_event(
        action="templates.create",
        status="success",
        actor=current_user,
        resource_type="prompt_template",
        resource_id=str(created.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Created prompt template “{created.name}”",
    )
    return created


@router.delete("/{template_id}", status_code=204)
def remove_template(
    template_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("templates:write")),
) -> None:
    """Delete a non-system prompt template."""
    delete_template(
        db,
        template_id,
        organization_id=current_user.organization_id,
    )
    record_event(
        action="templates.delete",
        status="success",
        actor=current_user,
        resource_type="prompt_template",
        resource_id=str(template_id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Deleted prompt template {template_id}",
    )
