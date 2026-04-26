"""Small encryption helper for vendor API secrets.

Existing plaintext rows remain readable. New rows are encrypted only when
VENDOR_API_KEY_ENCRYPTION_SECRET is configured, which lets us roll this out
without breaking current deployments.
"""

from __future__ import annotations

import base64
import hashlib

from app.config import get_settings


ENCRYPTED_PREFIX = "enc:v1:"


def encrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    secret = _encryption_secret()
    if not secret:
        return value
    token = _fernet(secret).encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value)
    if not raw.startswith(ENCRYPTED_PREFIX):
        return raw
    secret = _encryption_secret()
    if not secret:
        return None
    token = raw[len(ENCRYPTED_PREFIX) :]
    try:
        return _fernet(secret).decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def is_encrypted_secret(value: str | None) -> bool:
    return bool(value and str(value).startswith(ENCRYPTED_PREFIX))


def _encryption_secret() -> str | None:
    raw = get_settings().key_encryption_secret
    return raw.strip() if isinstance(raw, str) and raw.strip() else None


def _fernet(secret: str):
    from cryptography.fernet import Fernet

    encoded = secret.encode("utf-8")
    try:
        return Fernet(encoded)
    except Exception:
        key = base64.urlsafe_b64encode(hashlib.sha256(encoded).digest())
        return Fernet(key)
