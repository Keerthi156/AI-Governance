"""
RBAC admin service — list and update users within an organization.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.rbac import is_valid_role
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.rbac import UpdateUserRequest
from app.services.auth_service import user_to_response


def list_organization_users(db: Session, *, actor: User) -> list[UserResponse]:
    """List users that belong to the actor's organization."""
    rows = db.scalars(
        select(User)
        .options(joinedload(User.organization))
        .where(User.organization_id == actor.organization_id)
        .order_by(User.created_at.asc())
    ).all()
    return [user_to_response(row) for row in rows]


def count_org_admins(db: Session, organization_id: UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.organization_id == organization_id,
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
        or 0
    )


def update_organization_user(
    db: Session,
    *,
    actor: User,
    user_id: UUID,
    body: UpdateUserRequest,
) -> UserResponse:
    """Update role / active flag for a user in the actor's organization."""
    if body.role is None and body.is_active is None:
        raise ValidationAppError("Provide role and/or is_active to update")

    target = db.scalar(
        select(User)
        .options(joinedload(User.organization))
        .where(User.id == user_id)
    )
    if target is None:
        raise NotFoundError("User not found")
    if target.organization_id != actor.organization_id:
        raise ForbiddenError("Cannot manage users outside your organization")

    if body.role is not None:
        if not is_valid_role(body.role):
            raise ValidationAppError("Invalid role; expected viewer, member, or admin")
        if (
            target.id == actor.id
            and target.role == "admin"
            and body.role != "admin"
            and count_org_admins(db, actor.organization_id) <= 1
        ):
            raise ConflictError("Cannot demote the last active admin in the organization")
        target.role = body.role

    if body.is_active is not None:
        if (
            target.id == actor.id
            and body.is_active is False
            and target.role == "admin"
            and count_org_admins(db, actor.organization_id) <= 1
        ):
            raise ConflictError("Cannot deactivate the last active admin in the organization")
        target.is_active = body.is_active

    db.add(target)
    db.commit()
    db.refresh(target)
    reloaded = db.scalar(
        select(User)
        .options(joinedload(User.organization))
        .where(User.id == target.id)
    )
    assert reloaded is not None
    return user_to_response(reloaded)
