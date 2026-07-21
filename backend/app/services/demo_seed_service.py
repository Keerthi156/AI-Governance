"""
Seed demo accounts for local / shared demos.

Why this exists:
- Login page lists fixed test emails so visitors can try each role.
- Idempotent: creates missing users only; never overwrites passwords.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.services.auth_service import get_user_by_email
from app.services.organization_service import (
    DEFAULT_ORG_SLUG,
    ensure_membership,
    get_or_create_organization,
)

logger = logging.getLogger(__name__)

DEMO_PASSWORD = "changeme123"

# email, role, full_name
DEMO_ACCOUNTS: tuple[tuple[str, str, str], ...] = (
    ("demo@example.com", "admin", "Demo Admin"),
    ("member@example.com", "member", "Demo Member"),
    ("viewer@example.com", "viewer", "Demo Viewer"),
)


def seed_demo_accounts(db: Session) -> int:
    """Ensure demo users exist in the default org. Returns count created."""
    org = get_or_create_organization(db, slug=DEFAULT_ORG_SLUG)
    created = 0
    for email, role, full_name in DEMO_ACCOUNTS:
        existing = get_user_by_email(db, email)
        if existing is not None:
            ensure_membership(
                db,
                user_id=existing.id,
                organization_id=org.id,
                role=existing.role,
                commit=False,
            )
            continue
        user = User(
            organization_id=org.id,
            email=email.lower().strip(),
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name=full_name,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()
        ensure_membership(
            db,
            user_id=user.id,
            organization_id=org.id,
            role=role,
            commit=False,
        )
        created += 1
        logger.info("Seeded demo user %s (%s)", email, role)
    db.commit()
    return created
