"""
Prompt template service — list, create, delete, and seed defaults.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.organization import Organization
from app.models.prompt_template import PromptTemplate
from app.models.user import User
from app.schemas.prompt_template import PromptTemplateCreate, PromptTemplateResponse
from app.services.organization_service import get_or_create_organization

_DEFAULT_TEMPLATES: tuple[dict[str, str | None], ...] = (
    {
        "name": "Governance overview",
        "description": "Short enterprise AI governance explanation.",
        "body": (
            "Explain enterprise AI governance in two sentences, focusing on "
            "policy enforcement, auditability, and responsible model use."
        ),
        "default_provider": "groq",
        "default_model": "llama-3.1-8b-instant",
    },
    {
        "name": "Policy risk check",
        "description": "Ask the model to flag policy risks in a draft prompt.",
        "body": (
            "Review the following draft prompt for policy risks (secrets, PII, "
            "prohibited topics). List issues as bullets, or say 'No issues found'.\n\n"
            "Draft prompt:\n{{paste your draft here}}"
        ),
        "default_provider": "groq",
        "default_model": "llama-3.1-8b-instant",
    },
    {
        "name": "Executive summary",
        "description": "Summarize text for leadership.",
        "body": (
            "Summarize the following content for an executive audience in 5 "
            "bullet points. Keep each bullet under 20 words.\n\n"
            "Content:\n{{paste content here}}"
        ),
        "default_provider": "groq",
        "default_model": "llama-3.1-8b-instant",
    },
)


def _to_response(row: PromptTemplate, org: Organization) -> PromptTemplateResponse:
    return PromptTemplateResponse(
        id=row.id,
        organization_id=row.organization_id,
        organization_slug=org.slug,
        name=row.name,
        description=row.description,
        body=row.body,
        default_provider=row.default_provider,
        default_model=row.default_model,
        is_system=row.is_system,
        created_at=row.created_at,
    )


def ensure_default_templates(db: Session, *, organization_slug: str = "default") -> None:
    """Seed a few system templates when the org has none."""
    org = get_or_create_organization(db, slug=organization_slug.strip().lower())
    existing = db.scalar(
        select(PromptTemplate.id)
        .where(PromptTemplate.organization_id == org.id)
        .limit(1)
    )
    if existing is not None:
        return
    for item in _DEFAULT_TEMPLATES:
        db.add(
            PromptTemplate(
                organization_id=org.id,
                name=str(item["name"]),
                description=item.get("description"),
                body=str(item["body"]),
                default_provider=str(item.get("default_provider") or "groq"),
                default_model=item.get("default_model"),
                is_system=True,
            )
        )
    db.commit()


def list_templates(
    db: Session,
    *,
    organization_slug: str = "default",
) -> list[PromptTemplateResponse]:
    ensure_default_templates(db, organization_slug=organization_slug)
    org = get_or_create_organization(db, slug=organization_slug.strip().lower())
    rows = db.scalars(
        select(PromptTemplate)
        .where(PromptTemplate.organization_id == org.id)
        .order_by(PromptTemplate.is_system.desc(), PromptTemplate.name.asc())
    ).all()
    return [_to_response(row, org) for row in rows]


def create_template(
    db: Session,
    body: PromptTemplateCreate,
    *,
    actor: User | None = None,
) -> PromptTemplateResponse:
    name = body.name.strip()
    text = body.body.strip()
    if not name or not text:
        raise ValidationAppError("name and body are required")

    org = get_or_create_organization(db, slug=body.organization_slug.strip().lower())
    row = PromptTemplate(
        organization_id=org.id,
        created_by_user_id=actor.id if actor else None,
        name=name,
        description=body.description.strip() if body.description else None,
        body=text,
        default_provider=body.default_provider.strip().lower() or "groq",
        default_model=body.default_model.strip() if body.default_model else None,
        is_system=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row, org)


def delete_template(
    db: Session,
    template_id: UUID,
    *,
    organization_id: UUID,
) -> None:
    row = db.scalar(select(PromptTemplate).where(PromptTemplate.id == template_id))
    if row is None or row.organization_id != organization_id:
        raise NotFoundError("Prompt template not found")
    if row.is_system:
        raise ValidationAppError("System templates cannot be deleted")
    db.delete(row)
    db.commit()
