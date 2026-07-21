"""Reversible encryption for stored secrets (e.g. SMTP credentials).

New values are encrypted with authenticated Fernet encryption (see
:mod:`app.core.crypto`). Older values were stored with a legacy repeating-key
XOR scheme; :func:`decrypt_secret` transparently falls back to that legacy
decoder so existing records keep working until they are next re-saved (which
upgrades them to Fernet).
"""

from __future__ import annotations

import base64
import hashlib

from app.core import crypto
from app.core.config import SECRET_KEY


def _legacy_key() -> bytes:
    return hashlib.sha256(f"protrack-smtp:{SECRET_KEY}".encode()).digest()


def _legacy_decrypt(encrypted: str) -> str | None:
    try:
        key = _legacy_key()
        data = base64.urlsafe_b64decode(encrypted.encode())
        plain = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))
        return plain.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    return crypto.encrypt(plain)


def decrypt_secret(encrypted: str) -> str:
    if not encrypted:
        return ""
    decrypted = crypto.try_decrypt(encrypted)
    if decrypted is not None:
        return decrypted
    # Backward compatibility: value predates the Fernet migration.
    legacy = _legacy_decrypt(encrypted)
    return legacy if legacy is not None else ""
