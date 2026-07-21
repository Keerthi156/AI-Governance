"""
Organization helpers.

Why this exists:
- Prompt history and users are tenant-scoped; every write needs an organization.
- Memberships gate which tenants a caller may access via organization_slug.
- Auto-provisions a default org only for unauthenticated bootstrap (register).
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.rbac import is_valid_role
from app.models.membership import OrganizationMembership
from app.models.organization import Organization
from app.models.user import User

DEFAULT_ORG_SLUG = "default"
DEFAULT_ORG_NAME = "Default Organization"

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_request_actor: ContextVar[User | None] = ContextVar("org_request_actor", default=None)


def bind_request_actor(user: User | None) -> None:
    """Bind the authenticated user for tenant membership checks in this request."""
    _request_actor.set(user)


def get_request_actor() -> User | None:
    return _request_actor.get()


def get_organization_by_slug(db: Session, slug: str) -> Organization | None:
    cleaned = slug.strip().lower()
    return db.scalar(select(Organization).where(Organization.slug == cleaned))


def get_membership(
    db: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
) -> OrganizationMembership | None:
    return db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
    )


def user_is_org_member(db: Session, *, user_id: UUID, organization_id: UUID) -> bool:
    return get_membership(db, user_id=user_id, organization_id=organization_id) is not None


def ensure_membership(
    db: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    role: str = "member",
    commit: bool = True,
) -> OrganizationMembership:
    """Idempotently ensure a membership row exists."""
    existing = get_membership(db, user_id=user_id, organization_id=organization_id)
    if existing is not None:
        return existing
    if not is_valid_role(role):
        raise ValidationAppError(f"Invalid role '{role}'")
    row = OrganizationMembership(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def require_organization_access(
    db: Session,
    slug: str,
    *,
    actor: User | None = None,
) -> Organization:
    """
    Resolve an organization by slug and require membership when an actor is known.
    Does not auto-create tenants.
    """
    cleaned = slug.strip().lower() or DEFAULT_ORG_SLUG
    org = get_organization_by_slug(db, cleaned)
    if org is None:
        raise NotFoundError(f"Organization “{cleaned}” not found")

    user = actor if actor is not None else get_request_actor()
    if user is not None:
        from app.services.api_key_service import get_api_key_organization_id

        api_org_id = get_api_key_organization_id()
        if api_org_id is not None:
            if org.id != api_org_id:
                raise ForbiddenError(
                    f"API key is scoped to a different organization than “{cleaned}”"
                )
            return org
        if not user_is_org_member(db, user_id=user.id, organization_id=org.id):
            raise ForbiddenError(f"Not a member of organization “{cleaned}”")
    return org


def get_or_create_organization(
    db: Session,
    *,
    slug: str = DEFAULT_ORG_SLUG,
    name: str = DEFAULT_ORG_NAME,
) -> Organization:
    """
    Return an organization by slug.

    When a request actor is bound (authenticated API call), membership is required
    and missing orgs are NOT auto-created (prevents slug guessing / tenant escape).
    Unauthenticated bootstrap (register) may still create the org.
    """
    cleaned = slug.strip().lower() or DEFAULT_ORG_SLUG
    actor = get_request_actor()
    if actor is not None:
        return require_organization_access(db, cleaned, actor=actor)

    existing = get_organization_by_slug(db, cleaned)
    if existing is not None:
        return existing

    org = Organization(
        name=name if cleaned == DEFAULT_ORG_SLUG else name,
        slug=cleaned,
        description="Auto-created tenant for local development and early Phase 1 usage.",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def list_organizations_for_user(db: Session, user: User) -> list[Organization]:
    """Return organizations the user is a member of, ordered by slug."""
    return list(
        db.scalars(
            select(Organization)
            .join(
                OrganizationMembership,
                OrganizationMembership.organization_id == Organization.id,
            )
            .where(OrganizationMembership.user_id == user.id)
            .order_by(Organization.slug.asc())
        ).all()
    )


def list_organizations(db: Session) -> list[Organization]:
    """Return all organizations ordered by slug (admin / legacy)."""
    return list(
        db.scalars(select(Organization).order_by(Organization.slug.asc())).all()
    )


def create_organization(
    db: Session,
    *,
    name: str,
    slug: str,
    description: str | None = None,
    creator: User | None = None,
) -> Organization:
    """Create a named organization. Creator becomes an admin member when provided."""
    cleaned_slug = slug.strip().lower()
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValidationAppError("Organization name is required")
    if not _SLUG_RE.match(cleaned_slug):
        raise ValidationAppError(
            "Slug must be lowercase letters, numbers, and hyphens (e.g. acme-corp)"
        )

    existing_slug = get_organization_by_slug(db, cleaned_slug)
    if existing_slug is not None:
        raise ConflictError(f"Organization slug “{cleaned_slug}” already exists")

    existing_name = db.scalar(
        select(Organization).where(Organization.name == cleaned_name)
    )
    if existing_name is not None:
        raise ConflictError(f"Organization name “{cleaned_name}” already exists")

    org = Organization(
        name=cleaned_name,
        slug=cleaned_slug,
        description=description.strip() if description else None,
    )
    db.add(org)
    db.flush()
    if creator is not None:
        ensure_membership(
            db,
            user_id=creator.id,
            organization_id=org.id,
            role="admin",
            commit=False,
        )
    db.commit()
    db.refresh(org)
    return org


def _require_org_admin(db: Session, actor: User, org: Organization) -> None:
    membership = get_membership(db, user_id=actor.id, organization_id=org.id)
    if membership is None:
        raise ForbiddenError(f"Not a member of organization “{org.slug}”")
    if actor.role == "admin" or membership.role == "admin":
        return
    raise ForbiddenError("Organization admin membership required")


def list_organization_members(
    db: Session,
    *,
    slug: str,
    actor: User,
) -> list[OrganizationMembership]:
    org = require_organization_access(db, slug, actor=actor)
    return list(
        db.scalars(
            select(OrganizationMembership)
            .options(
                joinedload(OrganizationMembership.user).joinedload(User.organization),
                joinedload(OrganizationMembership.organization),
            )
            .where(OrganizationMembership.organization_id == org.id)
            .order_by(OrganizationMembership.created_at.asc())
        ).unique().all()
    )


def add_organization_member(
    db: Session,
    *,
    slug: str,
    actor: User,
    email: str,
    role: str = "member",
) -> OrganizationMembership:
    """Add an existing user to an organization by email."""
    org = require_organization_access(db, slug, actor=actor)
    _require_org_admin(db, actor, org)
    if not is_valid_role(role):
        raise ValidationAppError(f"Invalid role '{role}'")

    from app.services.auth_service import get_user_by_email

    target = get_user_by_email(db, email)
    if target is None:
        raise NotFoundError(f"No user with email “{email.strip().lower()}”")

    existing = get_membership(db, user_id=target.id, organization_id=org.id)
    if existing is not None:
        raise ConflictError(f"User is already a member of “{org.slug}”")

    row = OrganizationMembership(
        user_id=target.id,
        organization_id=org.id,
        role=role,
    )
    db.add(row)
    db.commit()
    return (
        db.scalar(
            select(OrganizationMembership)
            .options(
                joinedload(OrganizationMembership.user).joinedload(User.organization),
                joinedload(OrganizationMembership.organization),
            )
            .where(OrganizationMembership.id == row.id)
        )
        or row
    )


def remove_organization_member(
    db: Session,
    *,
    slug: str,
    actor: User,
    user_id: UUID,
) -> None:
    from sqlalchemy import func

    org = require_organization_access(db, slug, actor=actor)
    _require_org_admin(db, actor, org)

    membership = get_membership(db, user_id=user_id, organization_id=org.id)
    if membership is None:
        raise NotFoundError("Membership not found")

    if membership.role == "admin":
        count = (
            db.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(
                    OrganizationMembership.organization_id == org.id,
                    OrganizationMembership.role == "admin",
                )
            )
            or 0
        )
        if count <= 1:
            raise ValidationAppError("Cannot remove the last admin of an organization")

    db.delete(membership)
    db.commit()
