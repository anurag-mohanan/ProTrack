"""Symmetric encryption primitives for ProTrack stored secrets.

Prefers Fernet (AES-128-CBC + HMAC-SHA256, authenticated) from the
``cryptography`` library. The key is taken from ``PROTRACK_ENCRYPTION_KEY`` when
present; in development, where that env var is typically unset, a stable key is
derived from ``SECRET_KEY`` so the app keeps working without extra setup.

``cryptography`` is treated as an *optional* dependency: if it is not installed
the module falls back to a weaker (but still reversible) keyed-XOR encoding so
the application still boots and stored secrets keep round-tripping. This is a
safety net for deployments that upgraded the code without reinstalling
requirements — install ``requirements.txt`` to restore authenticated
encryption. The fallback is logged loudly at import time.
"""

from __future__ import annotations

import base64
import hashlib
import logging

from app.core.config import ENCRYPTION_KEY, SECRET_KEY

logger = logging.getLogger("protrack.startup")

try:
    from cryptography.fernet import Fernet, InvalidToken

    _CRYPTOGRAPHY_AVAILABLE = True
except Exception:  # ImportError, or any load-time failure
    _CRYPTOGRAPHY_AVAILABLE = False


if _CRYPTOGRAPHY_AVAILABLE:

    def _load_fernet() -> "Fernet":
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

else:
    logger.warning(
        "cryptography is not installed; stored secrets use a weaker reversible "
        "fallback encoding. Run 'pip install -r requirements.txt' to restore "
        "authenticated encryption."
    )

    _FALLBACK_PREFIX = "xorv1:"

    def _fallback_key() -> bytes:
        base = ENCRYPTION_KEY or SECRET_KEY
        return hashlib.sha256(f"protrack-fernet:{base}".encode()).digest()

    def _xor(data: bytes) -> bytes:
        key = _fallback_key()
        return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))

    def encrypt(plain: str) -> str:
        if not plain:
            return ""
        encoded = base64.urlsafe_b64encode(_xor(plain.encode("utf-8"))).decode("ascii")
        return _FALLBACK_PREFIX + encoded

    def decrypt(token: str) -> str:
        if not token:
            return ""
        if token.startswith(_FALLBACK_PREFIX):
            token = token[len(_FALLBACK_PREFIX):]
        data = base64.urlsafe_b64decode(token.encode("ascii"))
        return _xor(data).decode("utf-8")

    def try_decrypt(token: str) -> str | None:
        if not token:
            return ""
        # Only claim tokens we produced; let other blobs fall through to the
        # caller's legacy decoder.
        if not token.startswith(_FALLBACK_PREFIX):
            return None
        try:
            return decrypt(token)
        except (ValueError, UnicodeDecodeError):
            return None
