"""
BYOK provider credential service — encrypt, store, resolve org → env.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.credential_crypto import decrypt_secret, encrypt_secret, key_hint
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.provider_credential import OrganizationProviderCredential
from app.models.user import User
from app.schemas.provider_credential import (
    ProviderCredentialResponse,
    ProviderCredentialUpsert,
)
from app.services.organization_service import require_organization_access
from app.services.provider_registry import SUPPORTED_PROVIDERS

PROVIDER_ENV_ATTR = {
    "groq": "groq_api_key",
    "openai": "openai_api_key",
    "claude": "anthropic_api_key",
    "gemini": "google_api_key",
}


def _normalize_provider(provider: str) -> str:
    key = provider.strip().lower()
    if key not in SUPPORTED_PROVIDERS:
        raise ValidationAppError(
            f"Unsupported provider '{provider}'. Supported: {sorted(SUPPORTED_PROVIDERS)}"
        )
    return key


def env_key_for_provider(provider: str) -> str:
    settings = get_settings()
    attr = PROVIDER_ENV_ATTR.get(provider, "")
    value = getattr(settings, attr, "") if attr else ""
    return (value or "").strip()


def get_credential_row(
    db: Session,
    *,
    organization_id: UUID,
    provider: str,
) -> OrganizationProviderCredential | None:
    return db.scalar(
        select(OrganizationProviderCredential)
        .options(joinedload(OrganizationProviderCredential.organization))
        .where(
            OrganizationProviderCredential.organization_id == organization_id,
            OrganizationProviderCredential.provider == provider,
        )
    )


def resolve_provider_api_key(
    db: Session | None,
    *,
    organization_id: UUID | None,
    provider: str,
) -> str | None:
    """
    Resolve plaintext API key: org BYOK first, then platform env.
    Returns None when neither is configured.
    """
    provider_key = provider.strip().lower()
    if organization_id is not None and db is not None:
        row = get_credential_row(
            db, organization_id=organization_id, provider=provider_key
        )
        if row is not None and row.ciphertext:
            return decrypt_secret(row.ciphertext)

    env_key = env_key_for_provider(provider_key)
    return env_key or None


def list_provider_credentials(
    db: Session,
    *,
    actor: User,
    organization_slug: str,
) -> list[ProviderCredentialResponse]:
    org = require_organization_access(db, organization_slug, actor=actor)
    rows = {
        row.provider: row
        for row in db.scalars(
            select(OrganizationProviderCredential).where(
                OrganizationProviderCredential.organization_id == org.id
            )
        ).all()
    }
    result: list[ProviderCredentialResponse] = []
    for provider in sorted(SUPPORTED_PROVIDERS):
        row = rows.get(provider)
        env_configured = bool(env_key_for_provider(provider))
        if row is not None:
            source = "org"
            has_credential = True
        elif env_configured:
            source = "env"
            has_credential = True
        else:
            source = "none"
            has_credential = False
        result.append(
            ProviderCredentialResponse(
                id=row.id if row else None,
                provider=provider,
                organization_id=org.id,
                organization_slug=org.slug,
                has_credential=has_credential,
                key_hint=row.key_hint if row else None,
                source=source,
                env_configured=env_configured,
                notes=row.notes if row else None,
                updated_at=row.updated_at if row else None,
            )
        )
    return result


def upsert_provider_credential(
    db: Session,
    *,
    actor: User,
    provider: str,
    body: ProviderCredentialUpsert,
) -> ProviderCredentialResponse:
    provider_key = _normalize_provider(provider)
    org = require_organization_access(db, body.organization_slug, actor=actor)
    plaintext = body.api_key.strip()
    if len(plaintext) < 8:
        raise ValidationAppError("API key is too short")

    row = get_credential_row(db, organization_id=org.id, provider=provider_key)
    if row is None:
        row = OrganizationProviderCredential(
            organization_id=org.id,
            provider=provider_key,
            ciphertext=encrypt_secret(plaintext),
            key_hint=key_hint(plaintext),
            notes=body.notes.strip() if body.notes else None,
        )
        db.add(row)
    else:
        row.ciphertext = encrypt_secret(plaintext)
        row.key_hint = key_hint(plaintext)
        if body.notes is not None:
            row.notes = body.notes.strip() or None
        db.add(row)
    db.commit()
    db.refresh(row)

    return ProviderCredentialResponse(
        id=row.id,
        provider=provider_key,
        organization_id=org.id,
        organization_slug=org.slug,
        has_credential=True,
        key_hint=row.key_hint,
        source="org",
        env_configured=bool(env_key_for_provider(provider_key)),
        notes=row.notes,
        updated_at=row.updated_at,
    )


def delete_provider_credential(
    db: Session,
    *,
    actor: User,
    provider: str,
    organization_slug: str,
) -> ProviderCredentialResponse:
    provider_key = _normalize_provider(provider)
    org = require_organization_access(db, organization_slug, actor=actor)
    row = get_credential_row(db, organization_id=org.id, provider=provider_key)
    if row is None:
        raise NotFoundError(f"No org credential for provider '{provider_key}'")
    db.delete(row)
    db.commit()

    env_configured = bool(env_key_for_provider(provider_key))
    return ProviderCredentialResponse(
        id=None,
        provider=provider_key,
        organization_id=org.id,
        organization_slug=org.slug,
        has_credential=env_configured,
        key_hint=None,
        source="env" if env_configured else "none",
        env_configured=env_configured,
        notes=None,
        updated_at=None,
    )
