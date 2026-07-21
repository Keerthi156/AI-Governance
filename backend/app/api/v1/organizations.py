"""
Organization HTTP routes — list tenants, create, and manage memberships.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationInviteCreate,
    OrganizationInviteResponse,
    OrganizationMemberAdd,
    OrganizationMemberResponse,
    OrganizationResponse,
)
from app.services.audit_service import record_event
from app.services.invite_service import create_invite, list_invites, revoke_invite
from app.services.organization_service import (
    add_organization_member,
    create_organization,
    list_organization_members,
    list_organizations_for_user,
    remove_organization_member,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _member_to_response(row) -> OrganizationMemberResponse:
    return OrganizationMemberResponse(
        id=row.id,
        user_id=row.user_id,
        email=row.user.email,
        full_name=row.user.full_name,
        membership_role=row.role,
        organization_id=row.organization_id,
        organization_slug=row.organization.slug,
        created_at=row.created_at,
    )


@router.get("", response_model=list[OrganizationResponse])
def get_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organizations:read")),
) -> list[OrganizationResponse]:
    """List organizations the caller is a member of (org switcher)."""
    return [
        OrganizationResponse.model_validate(row)
        for row in list_organizations_for_user(db, current_user)
    ]


@router.post("", response_model=OrganizationResponse, status_code=201)
def post_organization(
    body: OrganizationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organizations:manage")),
) -> OrganizationResponse:
    """Create a new organization tenant; creator becomes an admin member."""
    org = create_organization(
        db,
        name=body.name,
        slug=body.slug,
        description=body.description,
        creator=current_user,
    )
    record_event(
        action="organizations.create",
        status="success",
        actor=current_user,
        resource_type="organization",
        resource_id=str(org.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Created organization “{org.name}” ({org.slug})",
        details={"slug": org.slug},
    )
    return OrganizationResponse.model_validate(org)


@router.get("/{slug}/members", response_model=list[OrganizationMemberResponse])
def get_organization_members(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organizations:read")),
) -> list[OrganizationMemberResponse]:
    """List members of an organization (caller must be a member)."""
    rows = list_organization_members(db, slug=slug, actor=current_user)
    return [_member_to_response(row) for row in rows]


@router.post(
    "/{slug}/members",
    response_model=OrganizationMemberResponse,
    status_code=201,
)
def post_organization_member(
    slug: str,
    body: OrganizationMemberAdd,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organizations:read")),
) -> OrganizationMemberResponse:
    """Add an existing user to an organization (org admin or platform admin)."""
    row = add_organization_member(
        db,
        slug=slug,
        actor=current_user,
        email=str(body.email),
        role=body.role,
    )
    record_event(
        action="organizations.member_add",
        status="success",
        actor=current_user,
        resource_type="organization",
        resource_id=str(row.organization_id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Added {row.user.email} to {row.organization.slug}",
        details={
            "slug": row.organization.slug,
            "member_email": row.user.email,
            "membership_role": row.role,
        },
    )
    return _member_to_response(row)


@router.get("/{slug}/invites", response_model=list[OrganizationInviteResponse])
def get_organization_invites(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organizations:read")),
) -> list[OrganizationInviteResponse]:
    """List invites for an organization (org admin)."""
    return list_invites(db, slug=slug, actor=current_user)


@router.post(
    "/{slug}/invites",
    response_model=OrganizationInviteResponse,
    status_code=201,
)
def post_organization_invite(
    slug: str,
    body: OrganizationInviteCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organizations:read")),
) -> OrganizationInviteResponse:
    """Create an invite token (plaintext returned once)."""
    created = create_invite(db, slug=slug, actor=current_user, body=body)
    record_event(
        action="organizations.invite_create",
        status="success",
        actor=current_user,
        resource_type="organization_invite",
        resource_id=str(created.id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Created invite for {created.organization_slug}",
        details={
            "email": created.email,
            "role": created.role,
            "expires_at": created.expires_at.isoformat(),
        },
    )
    return created


@router.delete("/{slug}/invites/{invite_id}", status_code=204)
def delete_organization_invite(
    slug: str,
    invite_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organizations:read")),
) -> None:
    """Revoke an unused invite."""
    revoke_invite(db, slug=slug, actor=current_user, invite_id=invite_id)
    record_event(
        action="organizations.invite_revoke",
        status="success",
        actor=current_user,
        resource_type="organization_invite",
        resource_id=str(invite_id),
        request_id=getattr(request.state, "request_id", None),
        summary=f"Revoked invite {invite_id} for {slug}",
    )


@router.delete("/{slug}/members/{user_id}", status_code=204)
def delete_organization_member(
    slug: str,
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organizations:read")),
) -> None:
    """Remove a member from an organization (org admin or platform admin)."""
    remove_organization_member(db, slug=slug, actor=current_user, user_id=user_id)
    record_event(
        action="organizations.member_remove",
        status="success",
        actor=current_user,
        resource_type="organization",
        request_id=getattr(request.state, "request_id", None),
        summary=f"Removed member {user_id} from {slug}",
        details={"slug": slug, "member_user_id": str(user_id)},
    )
