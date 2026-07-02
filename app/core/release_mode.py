"""Release-mode helpers for internal soft launch vs production enforcement."""

from app.core.config import INTERNAL_RELEASE


def is_internal_release() -> bool:
    return INTERNAL_RELEASE


def effective_must_change_password(stored_value: bool) -> bool:
    """Return whether the client should enforce a mandatory password change."""
    if is_internal_release():
        return False
    return stored_value
