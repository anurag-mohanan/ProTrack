"""Security Center: governance overview, editable policy, active sessions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db
from app.core import config
from app.models.enums import ActivityAction, EntityType
from app.models.models import Activity, LoginSession, User
from app.services.activity_service import log_activity, OUTCOME_SUCCESS
from app.services.backup_service import list_database_backups
from app.services.security_policy_service import get_effective_policy, update_policy

router = APIRouter(prefix="/admin/security", tags=["security"])
admin = Depends(require_roles("Admin"))


class SecurityPolicyModel(BaseModel):
    password_min_length: int
    password_expiry_days: int
    password_history_count: int
    lockout_max_failed_attempts: int
    lockout_duration_minutes: int
    session_idle_timeout_minutes: int
    audit_retention_days: int
    require_sso_for_admins: bool = False


class SecurityPolicyUpdate(BaseModel):
    password_min_length: int | None = None
    password_expiry_days: int | None = None
    password_history_count: int | None = None
    lockout_max_failed_attempts: int | None = None
    lockout_duration_minutes: int | None = None
    session_idle_timeout_minutes: int | None = None
    audit_retention_days: int | None = None
    require_sso_for_admins: bool | None = None


class ActiveSession(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str | None = None
    user_email: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime | None = None
    last_seen_at: datetime | None = None
    expires_at: datetime | None = None


class SecurityEvent(BaseModel):
    action: str
    outcome: str | None = None
    module: str | None = None
    ip_address: str | None = None
    user_id: UUID | None = None
    created_at: datetime | None = None


class SecurityOverview(BaseModel):
    security_score: int
    failed_logins_24h: int
    locked_accounts: int
    active_sessions: int
    recent_permission_changes: int
    export_events_7d: int
    last_backup_at: datetime | None = None
    last_backup_filename: str | None = None
    secret_ok: bool
    encryption_ok: bool
    hsts_enabled: bool
    rate_limiting_enabled: bool
    config_warnings: list[str]
    recent_events: list[SecurityEvent]


def _now() -> datetime:
    return datetime.now(UTC)


@router.get("/policy", response_model=SecurityPolicyModel, dependencies=[admin])
def read_security_policy(db: Session = Depends(get_db)):
    return SecurityPolicyModel(**get_effective_policy(db).__dict__)


@router.put("/policy", response_model=SecurityPolicyModel, dependencies=[admin])
def write_security_policy(
    payload: SecurityPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "require_sso_for_admins":
            continue
        if value is not None and value < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{key} must be zero or greater.",
            )
    effective = update_policy(db, updates, current_user)
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.settings,
        entity_id=current_user.id,
        action=ActivityAction.settings_updated,
        new_value={"security_policy": updates},
        outcome=OUTCOME_SUCCESS,
        module="system_administration",
    )
    return SecurityPolicyModel(**effective.__dict__)


@router.get("/sessions", response_model=list[ActiveSession], dependencies=[admin])
def list_active_sessions(db: Session = Depends(get_db)):
    now = _now()
    rows = db.scalars(
        select(LoginSession)
        .where(LoginSession.revoked.is_(False))
        .order_by(LoginSession.created_at.desc())
        .limit(200)
    ).all()
    out: list[ActiveSession] = []
    for row in rows:
        # A session is "active" only while its most-recent token could still be valid.
        if row.expires_at is not None:
            expires = row.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if expires < now:
                continue
        user = db.get(User, row.user_id)
        # Skip sessions superseded by a token_version bump (force-logout).
        if user is not None and int(user.token_version or 0) != int(row.token_version or 0):
            continue
        out.append(
            ActiveSession(
                id=row.id,
                user_id=row.user_id,
                user_name=(f"{user.first_name} {user.last_name}".strip() if user else None),
                user_email=user.email if user else None,
                ip_address=row.ip_address,
                user_agent=row.user_agent,
                created_at=row.created_at,
                last_seen_at=row.last_seen_at,
                expires_at=row.expires_at,
            )
        )
    return out


@router.post("/sessions/{user_id}/terminate", dependencies=[admin])
def terminate_user_sessions(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.token_version = int(user.token_version or 0) + 1
    db.add(user)
    db.query(LoginSession).filter(
        LoginSession.user_id == user_id,
        LoginSession.revoked.is_(False),
    ).update({LoginSession.revoked: True}, synchronize_session=False)
    db.commit()
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.user,
        entity_id=user_id,
        action=ActivityAction.user_logged_out,
        new_value={"terminated_sessions_for": str(user_id)},
        outcome=OUTCOME_SUCCESS,
        module="system_administration",
    )
    return {"message": "All sessions for the user have been terminated."}


@router.get("/overview", response_model=SecurityOverview, dependencies=[admin])
def security_overview(db: Session = Depends(get_db)):
    now = _now()
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    failed_logins_24h = (
        db.scalar(
            select(func.count(Activity.id)).where(
                Activity.action == ActivityAction.login_failed,
                Activity.created_at >= since_24h,
            )
        )
        or 0
    )
    locked_accounts = (
        db.scalar(
            select(func.count(User.id)).where(
                User.is_deleted.is_(False),
                (User.is_locked.is_(True)) | (User.locked_until > now),
            )
        )
        or 0
    )
    active_sessions = len(list_active_sessions(db))
    recent_permission_changes = (
        db.scalar(
            select(func.count(Activity.id)).where(
                Activity.action.in_(
                    [
                        ActivityAction.password_reset,
                        ActivityAction.admin_impersonation_started,
                        ActivityAction.user_archived,
                        ActivityAction.user_restored,
                    ]
                ),
                Activity.created_at >= since_7d,
            )
        )
        or 0
    )
    export_events_7d = (
        db.scalar(
            select(func.count(Activity.id)).where(
                Activity.action == ActivityAction.data_exported,
                Activity.created_at >= since_7d,
            )
        )
        or 0
    )

    backups = list_database_backups()
    last_backup_at = None
    last_backup_filename = None
    if backups:
        first = backups[0]
        last_backup_filename = first.get("filename")
        modified = first.get("modified_at")
        if isinstance(modified, datetime):
            last_backup_at = modified

    problems = config.security_config_problems()
    secret_ok = config.SECRET_KEY != config.DEV_DEFAULT_SECRET_KEY
    encryption_ok = bool(config.ENCRYPTION_KEY)

    recent_events_rows = db.scalars(
        select(Activity)
        .where(Activity.outcome.is_not(None))
        .order_by(Activity.created_at.desc())
        .limit(15)
    ).all()
    recent_events = [
        SecurityEvent(
            action=row.action.value if hasattr(row.action, "value") else str(row.action),
            outcome=row.outcome,
            module=row.module,
            ip_address=row.ip_address,
            user_id=row.user_id,
            created_at=row.created_at,
        )
        for row in recent_events_rows
    ]

    # Simple weighted security score.
    score = 100
    if not secret_ok:
        score -= 25
    if not encryption_ok:
        score -= 20
    if config.INTERNAL_RELEASE:
        score -= 10
    if not config.ENABLE_HSTS:
        score -= 5
    if not config.RATE_LIMIT_ENABLED:
        score -= 10
    if locked_accounts > 0:
        score -= 5
    if failed_logins_24h > 25:
        score -= 5
    if not backups:
        score -= 10
    score = max(0, min(100, score))

    return SecurityOverview(
        security_score=score,
        failed_logins_24h=int(failed_logins_24h),
        locked_accounts=int(locked_accounts),
        active_sessions=int(active_sessions),
        recent_permission_changes=int(recent_permission_changes),
        export_events_7d=int(export_events_7d),
        last_backup_at=last_backup_at,
        last_backup_filename=last_backup_filename,
        secret_ok=secret_ok,
        encryption_ok=encryption_ok,
        hsts_enabled=config.ENABLE_HSTS,
        rate_limiting_enabled=config.RATE_LIMIT_ENABLED,
        config_warnings=problems,
        recent_events=recent_events,
    )
