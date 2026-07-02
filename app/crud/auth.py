from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.crud.base import select
from app.models.models import User


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
    if user.is_locked:
        return None, AuthFailureReason.locked
    if not verify_password(password, user.password_hash):
        return None, AuthFailureReason.wrong_password
    return user, None


def record_failed_login_attempt(db: Session, user: User) -> None:
    user.failed_login_count += 1
    db.add(user)
    db.commit()


def reset_login_lock(db: Session, user: User) -> User:
    user.is_locked = False
    user.failed_login_count = 0
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
