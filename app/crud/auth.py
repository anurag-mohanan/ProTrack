from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.crud.base import select
from app.models.models import User


def _now() -> datetime:
    return datetime.now(UTC)


def _is_locked_out(user: User) -> bool:
    locked_until = getattr(user, "locked_until", None)
    if locked_until is None:
        return False
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=UTC)
    return locked_until > _now()


class AuthFailureReason(StrEnum):
    user_not_found = "user_not_found"
    wrong_password = "wrong_password"
    inactive = "inactive"
    deleted = "deleted"
    archived = "archived"
    locked = "locked"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    normalized = normalize_email(email)
    return db.scalar(
        select(User).where(func.lower(User.email) == normalized)
    )


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> tuple[User | None, AuthFailureReason | None]:
    user = get_user_by_email(db, email)
    if user is None:
        return None, AuthFailureReason.user_not_found
    if user.is_deleted:
        return None, AuthFailureReason.deleted
    if not user.is_active:
        return None, AuthFailureReason.inactive
    if user.is_archived:
        return None, AuthFailureReason.archived
    if user.is_locked or _is_locked_out(user):
        return None, AuthFailureReason.locked
    if not verify_password(password, user.password_hash):
        return None, AuthFailureReason.wrong_password
    return user, None


def record_failed_login_attempt(db: Session, user: User) -> None:
    from app.services.security_policy_service import get_effective_policy

    policy = get_effective_policy(db)
    user.failed_login_count += 1
    # Automatic temporary lockout after too many consecutive failures.
    if (
        policy.lockout_max_failed_attempts > 0
        and user.failed_login_count >= policy.lockout_max_failed_attempts
    ):
        user.locked_until = _now() + timedelta(minutes=policy.lockout_duration_minutes)
    db.add(user)
    db.commit()


def reset_login_lock(db: Session, user: User) -> User:
    user.is_locked = False
    user.failed_login_count = 0
    user.locked_until = None
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
