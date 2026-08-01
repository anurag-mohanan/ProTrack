"""OIDC user resolution — link-only (no auto-provision) for R10 spike."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import User


def resolve_user_for_oidc(
    db: Session,
    *,
    subject: str,
    email: str | None,
) -> tuple[User | None, str | None]:
    """Return (user, error_reason). Link-only: existing users only."""
    by_subject = db.scalar(select(User).where(User.sso_subject == subject))
    if by_subject is not None:
        if not by_subject.is_active or by_subject.is_deleted or by_subject.is_archived:
            return None, "account_inactive"
        return by_subject, None

    if not email:
        return None, "email_missing"

    by_email = db.scalar(select(User).where(User.email == email.lower()))
    if by_email is None:
        return None, "no_local_user"

    if not by_email.is_active or by_email.is_deleted or by_email.is_archived:
        return None, "account_inactive"

    # First successful SSO: bind subject.
    if by_email.sso_subject and by_email.sso_subject != subject:
        return None, "sso_subject_conflict"

    by_email.sso_subject = subject
    db.add(by_email)
    db.flush()
    return by_email, None
