"""Symmetric encryption primitives for ProTrack stored secrets.

Uses Fernet (AES-128-CBC + HMAC-SHA256, authenticated) from the ``cryptography``
library. The key is taken from ``PROTRACK_ENCRYPTION_KEY`` when present; in
development, where that env var is typically unset, a stable key is derived from
``SECRET_KEY`` so the app keeps working without extra setup. Production is
required to supply a real key (enforced by ``config.assert_production_security``).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import ENCRYPTION_KEY, SECRET_KEY


def _load_fernet() -> Fernet:
    if ENCRYPTION_KEY:
        # Accept either a proper urlsafe-base64 32-byte Fernet key, or any
        # passphrase (which we hash down to a valid key).
        try:
            return Fernet(ENCRYPTION_KEY.encode())
        except (ValueError, TypeError):
            digest = hashlib.sha256(ENCRYPTION_KEY.encode()).digest()
            return Fernet(base64.urlsafe_b64encode(digest))
    # Development fallback: derive a deterministic key from SECRET_KEY.
    digest = hashlib.sha256(f"protrack-fernet:{SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


_fernet = _load_fernet()


def encrypt(plain: str) -> str:
    if not plain:
        return ""
    return _fernet.encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    if not token:
        return ""
    return _fernet.decrypt(token.encode("ascii")).decode("utf-8")


def try_decrypt(token: str) -> str | None:
    """Decrypt, returning ``None`` if the token is not valid Fernet ciphertext."""
    if not token:
        return ""
    try:
        return decrypt(token)
    except (InvalidToken, ValueError, TypeError):
        return None
