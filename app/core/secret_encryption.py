"""Reversible encryption for stored SMTP credentials."""

from __future__ import annotations

import base64
import hashlib

from app.core.config import SECRET_KEY


def _derive_key() -> bytes:
    return hashlib.sha256(f"protrack-smtp:{SECRET_KEY}".encode()).digest()


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    key = _derive_key()
    encrypted = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(plain.encode()))
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_secret(encrypted: str) -> str:
    if not encrypted:
        return ""
    key = _derive_key()
    data = base64.urlsafe_b64decode(encrypted.encode())
    plain = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))
    return plain.decode()
