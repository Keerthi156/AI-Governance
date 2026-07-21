"""
Fernet helpers for encrypting org provider credentials at rest.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.exceptions import AppException


def _fernet() -> Fernet:
    settings = get_settings()
    material = (settings.credential_encryption_key or settings.jwt_secret_key).strip()
    if not material:
        raise AppException(
            "Credential encryption key is not configured",
            code="credential_encryption_not_configured",
            status_code=500,
        )
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise AppException(
            "Failed to decrypt provider credential (wrong encryption key?)",
            code="credential_decrypt_failed",
            status_code=500,
        ) from exc


def key_hint(plaintext: str) -> str:
    """Short masked hint for UI (never the full secret)."""
    cleaned = plaintext.strip()
    if len(cleaned) <= 8:
        return "••••"
    return f"{cleaned[:4]}…{cleaned[-4:]}"
