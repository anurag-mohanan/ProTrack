"""Effective security policy resolution and persistence.

The shipped defaults live in :mod:`app.core.config` (env-driven). Admins may
override them at runtime via the Security Center; overrides are stored in the
``security_policy_settings`` singleton row. ``get_effective_policy`` merges the
two so enforcement code has a single source of truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.models.models import SecurityPolicySetting, User


@dataclass(frozen=True)
class EffectiveSecurityPolicy:
    password_min_length: int
    password_expiry_days: int
    password_history_count: int
    lockout_max_failed_attempts: int
    lockout_duration_minutes: int
    session_idle_timeout_minutes: int
    audit_retention_days: int
    require_sso_for_admins: bool


# Baseline password minimum enforced by the password policy module.
_DEFAULT_PASSWORD_MIN_LENGTH = 8
_DEFAULT_AUDIT_RETENTION_DAYS = 365

SSO_PRIVILEGED_ROLES = frozenset({"Admin", "System Admin"})


def sso_break_glass() -> bool:
    return os.getenv("PROTRACK_SSO_BREAK_GLASS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_policy_row(db: Session) -> SecurityPolicySetting | None:
    return db.scalar(select(SecurityPolicySetting).limit(1))


def _pick(override: int | None, default: int) -> int:
    return override if override is not None else default


def get_effective_policy(db: Session) -> EffectiveSecurityPolicy:
    row = get_policy_row(db)
    if row is None:
        return EffectiveSecurityPolicy(
            password_min_length=_DEFAULT_PASSWORD_MIN_LENGTH,
            password_expiry_days=config.PASSWORD_EXPIRY_DAYS,
            password_history_count=config.PASSWORD_HISTORY_COUNT,
            lockout_max_failed_attempts=config.LOCKOUT_MAX_FAILED_ATTEMPTS,
            lockout_duration_minutes=config.LOCKOUT_DURATION_MINUTES,
            session_idle_timeout_minutes=config.SESSION_IDLE_TIMEOUT_MINUTES,
            audit_retention_days=_DEFAULT_AUDIT_RETENTION_DAYS,
            require_sso_for_admins=False,
        )
    return EffectiveSecurityPolicy(
        password_min_length=_pick(row.password_min_length, _DEFAULT_PASSWORD_MIN_LENGTH),
        password_expiry_days=_pick(row.password_expiry_days, config.PASSWORD_EXPIRY_DAYS),
        password_history_count=_pick(row.password_history_count, config.PASSWORD_HISTORY_COUNT),
        lockout_max_failed_attempts=_pick(
            row.lockout_max_failed_attempts, config.LOCKOUT_MAX_FAILED_ATTEMPTS
        ),
        lockout_duration_minutes=_pick(
            row.lockout_duration_minutes, config.LOCKOUT_DURATION_MINUTES
        ),
        session_idle_timeout_minutes=_pick(
            row.session_idle_timeout_minutes, config.SESSION_IDLE_TIMEOUT_MINUTES
        ),
        audit_retention_days=_pick(row.audit_retention_days, _DEFAULT_AUDIT_RETENTION_DAYS),
        require_sso_for_admins=bool(getattr(row, "require_sso_for_admins", False)),
    )


def update_policy(
    db: Session,
    updates: dict[str, int | bool | None],
    updated_by: User | None,
) -> EffectiveSecurityPolicy:
    row = get_policy_row(db)
    if row is None:
        row = SecurityPolicySetting()
        db.add(row)
    int_keys = {
        "password_min_length",
        "password_expiry_days",
        "password_history_count",
        "lockout_max_failed_attempts",
        "lockout_duration_minutes",
        "session_idle_timeout_minutes",
        "audit_retention_days",
    }
    for key, value in updates.items():
        if key in int_keys:
            setattr(row, key, value)
        elif key == "require_sso_for_admins" and value is not None:
            row.require_sso_for_admins = bool(value)
    row.updated_at = datetime.now(UTC)
    row.updated_by_id = updated_by.id if updated_by is not None else None
    db.commit()
    return get_effective_policy(db)
