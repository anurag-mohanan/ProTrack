"""IT user account metadata and one-time credential generation."""

from __future__ import annotations

import secrets
import string
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_control import MODULE_IT_OPERATIONS
from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import ITUserAccount
from app.models.models import User
from app.services.activity_service import log_activity

MODULE = MODULE_IT_OPERATIONS
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"


def _generate_password(length: int = 16) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def list_accounts(
    db: Session,
    *,
    user_id: UUID | None = None,
    status: str | None = None,
) -> list[ITUserAccount]:
    stmt = select(ITUserAccount).order_by(ITUserAccount.account_type, ITUserAccount.username)
    if user_id is not None:
        stmt = stmt.where(ITUserAccount.user_id == user_id)
    if status:
        stmt = stmt.where(ITUserAccount.status == status)
    return list(db.scalars(stmt).all())


def get_account(db: Session, account_id: UUID) -> ITUserAccount | None:
    return db.get(ITUserAccount, account_id)


def create_account(
    db: Session,
    *,
    actor: User,
    user_id: UUID,
    account_type: str,
    username: str | None = None,
    display_name: str | None = None,
    status: str = "active",
    created_date: date | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> ITUserAccount:
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ProTrackValidationError("User not found.")
    acct_type = account_type.strip().lower()
    if not acct_type:
        raise ProTrackValidationError("account_type is required.")
    account = ITUserAccount(
        id=uuid4(),
        user_id=user_id,
        account_type=acct_type,
        username=(username or "").strip() or None,
        display_name=(display_name or "").strip() or None,
        status=(status or "active").strip().lower(),
        created_date=created_date or date.today(),
        notes=(notes or "").strip() or None,
    )
    db.add(account)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_account,
        entity_id=account.id,
        action=ActivityAction.it_account_created,
        new_value={
            "user_id": str(user_id),
            "account_type": account.account_type,
            "username": account.username,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(account)
    return account


def update_account(
    db: Session,
    account: ITUserAccount,
    *,
    actor: User,
    username: str | None = None,
    display_name: str | None = None,
    status: str | None = None,
    deactivated_date: date | None = None,
    notes: str | None = None,
    fields_set: set[str] | None = None,
) -> ITUserAccount:
    touched = fields_set or set()
    old_status = account.status
    if "username" in touched or (fields_set is None and username is not None):
        account.username = (username or "").strip() or None
    if "display_name" in touched or (fields_set is None and display_name is not None):
        account.display_name = (display_name or "").strip() or None
    if "status" in touched or (fields_set is None and status is not None):
        account.status = (status or account.status).strip().lower()
        if account.status == "deactivated" and account.deactivated_date is None:
            account.deactivated_date = deactivated_date or date.today()
    if "deactivated_date" in touched or (fields_set is None and deactivated_date is not None):
        account.deactivated_date = deactivated_date
    if "notes" in touched or (fields_set is None and notes is not None):
        account.notes = (notes or "").strip() or None
    db.add(account)
    db.flush()
    action = (
        ActivityAction.it_account_deactivated
        if account.status == "deactivated" and old_status != "deactivated"
        else ActivityAction.it_account_created
    )
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_account,
        entity_id=account.id,
        action=action,
        new_value={
            "username": account.username,
            "status": account.status,
            "updated": True,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(account)
    return account


def generate_credential(
    db: Session,
    *,
    actor: User,
    user_id: UUID,
    account_type: str,
    username: str | None = None,
) -> tuple[ITUserAccount, str]:
    """Create/update account metadata and return a one-time password (never persisted)."""
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ProTrackValidationError("User not found.")
    acct_type = account_type.strip().lower()
    if not acct_type:
        raise ProTrackValidationError("account_type is required.")

    account = db.scalar(
        select(ITUserAccount).where(
            ITUserAccount.user_id == user_id,
            ITUserAccount.account_type == acct_type,
            ITUserAccount.status != "deactivated",
        )
    )
    resolved_username = (username or "").strip() or None
    created_new = False
    if account is None:
        account = ITUserAccount(
            id=uuid4(),
            user_id=user_id,
            account_type=acct_type,
            username=resolved_username,
            display_name=f"{user.first_name} {user.last_name}".strip() or None,
            status="active",
            created_date=date.today(),
        )
        db.add(account)
        created_new = True
    else:
        if resolved_username:
            account.username = resolved_username
        account.status = "active"
        db.add(account)

    one_time_password = _generate_password(16)
    db.flush()
    if created_new:
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_account,
            entity_id=account.id,
            action=ActivityAction.it_account_created,
            new_value={
                "username": account.username,
                "account_type": account.account_type,
            },
            outcome="success",
            module=MODULE,
            commit=False,
        )
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_account,
        entity_id=account.id,
        action=ActivityAction.it_credential_generated,
        new_value={
            "username": account.username,
            "account_type": account.account_type,
            "user_id": str(user_id),
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(account)
    return account, one_time_password
