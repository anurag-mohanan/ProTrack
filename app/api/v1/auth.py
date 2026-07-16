import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db
from app.core.auth import create_access_token, decode_access_token
from app.core.permissions import get_role_name, get_user_permission_keys
from app.core.timesheet_eligibility import (
    user_can_enter_own_timesheet,
    user_requires_timesheet,
)
from app.core.team_access import user_can_view_organization_chart
from app.core.access_control import (
    resolve_user_modules,
    resolve_user_special_permissions,
)
from app.core.security import hash_password, verify_password
from app.crud.auth import (
    AuthFailureReason,
    authenticate_user,
    get_user_by_email,
    record_failed_login_attempt,
)
from app.crud import user as user_crud
from app.models.enums import ActivityAction, EntityType
from app.models.models import Team, User
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    CurrentUserRead,
    LoginRequest,
    Token,
    TokenPayload,
    UserProfileRead,
)
from app.core.release_mode import effective_must_change_password
from app.services.activity_service import log_activity
from app.services.user_team_service import list_user_team_assignments

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

FAILED_LOGIN_ENTITY_ID = UUID("00000000-0000-0000-0000-000000000001")

_AUTH_FAILURE_LOG_MESSAGES = {
    AuthFailureReason.user_not_found: "Login failed: user not found (email=%s)",
    AuthFailureReason.wrong_password: "Login failed: wrong password (email=%s)",
    AuthFailureReason.inactive: "Login failed: inactive account (email=%s)",
    AuthFailureReason.deleted: "Login failed: deleted account (email=%s)",
    AuthFailureReason.archived: "Login failed: archived account (email=%s)",
    AuthFailureReason.locked: "Login failed: locked account (email=%s)",
}


def get_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> TokenPayload:
    try:
        return decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _team_context(db: Session, user: User) -> tuple[UUID | None, str | None, list[UUID], list[str]]:
    assignments = list_user_team_assignments(db, user.id)
    team_ids: list[UUID] = []
    team_names: list[str] = []
    primary_team_id: UUID | None = user.team_id
    primary_team_name: str | None = None
    for membership in assignments:
        team = db.get(Team, membership.team_id)
        if team is None:
            continue
        team_ids.append(team.id)
        team_names.append(team.name)
        if membership.is_primary or membership.team_id == user.team_id:
            primary_team_id = team.id
            primary_team_name = team.name
    if primary_team_id is not None and primary_team_name is None:
        team = db.get(Team, primary_team_id)
        primary_team_name = team.name if team is not None else None
    if not team_ids and user.team_id is not None:
        team = db.get(Team, user.team_id)
        if team is not None:
            team_ids = [team.id]
            team_names = [team.name]
            primary_team_name = team.name
    return primary_team_id, primary_team_name, team_ids, team_names


def _issue_token(
    db: Session,
    user: User,
    *,
    impersonator_id: UUID | None = None,
) -> Token:
    role_name = get_role_name(db, user)
    team_id, team_name, team_ids, team_names = _team_context(db, user)
    try:
        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            name=f"{user.first_name} {user.last_name}",
            role=role_name,
            permissions=get_user_permission_keys(db, user),
            team_id=team_id,
            team_name=team_name,
            team_ids=team_ids,
            team_names=team_names,
            impersonator_id=impersonator_id,
        )
    except Exception:
        logger.exception("JWT generation failed for user_id=%s email=%s", user.id, user.email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Incorrect email or password",
        ) from None
    return Token(access_token=access_token)


def _log_failed_login(
    db: Session,
    email: str,
    reason: AuthFailureReason | None,
) -> None:
    if reason is not None:
        log_template = _AUTH_FAILURE_LOG_MESSAGES.get(reason)
        if log_template:
            logger.warning(log_template, email)

    existing = get_user_by_email(db, email)
    if existing is not None and reason == AuthFailureReason.wrong_password:
        record_failed_login_attempt(db, existing)

    log_activity(
        db,
        user=existing,
        entity_type=EntityType.user,
        entity_id=existing.id if existing is not None else FAILED_LOGIN_ENTITY_ID,
        action=ActivityAction.login_failed,
        new_value=f"{email}:{reason.value if reason else 'unknown'}",
    )


def _complete_login(db: Session, user: User) -> Token:
    user.last_login = datetime.now(UTC)
    user.failed_login_count = 0
    db.add(user)
    db.commit()
    db.refresh(user)
    log_activity(
        db,
        user=user,
        entity_type=EntityType.user,
        entity_id=user.id,
        action=ActivityAction.user_logged_in,
        new_value=user.email,
    )
    return _issue_token(db, user)


def _build_current_user_read(
    db: Session,
    user: User,
    token_payload: TokenPayload | None = None,
) -> CurrentUserRead:
    impersonator_name = None
    impersonator_id = token_payload.impersonator_id if token_payload else None
    if impersonator_id is not None:
        impersonator = db.get(User, impersonator_id)
        if impersonator is not None:
            impersonator_name = f"{impersonator.first_name} {impersonator.last_name}"
    role_name = get_role_name(db, user)
    _, team_name, team_ids, team_names = _team_context(db, user)
    return CurrentUserRead(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role_id=user.role_id,
        role_name=role_name,
        team_id=user.team_id,
        team_name=team_name,
        team_ids=team_ids,
        team_names=team_names,
        is_active=user.is_active,
        must_change_password=effective_must_change_password(user.must_change_password),
        last_login=user.last_login,
        impersonator_id=impersonator_id,
        impersonator_name=impersonator_name,
        module_access=resolve_user_modules(user, role_name),
        special_permissions=resolve_user_special_permissions(user, role_name),
        requires_timesheet=user_requires_timesheet(user),
        can_enter_own_timesheet=user_can_enter_own_timesheet(db, user),
        can_view_organization_chart=user_can_view_organization_chart(db, user),
    )


def _handle_login(db: Session, email: str, password: str) -> Token:
    try:
        user, reason = authenticate_user(db, email=email, password=password)
    except Exception:
        logger.exception("Database error during login for email=%s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    if user is None:
        _log_failed_login(db, email, reason)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _complete_login(db, user)


@router.post("/login", response_model=Token)
def login_json(body: LoginRequest, db: Session = Depends(get_db)):
    return _handle_login(db, body.email, body.password)


@router.post("/token", response_model=Token)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2-compatible token endpoint for Swagger Authorize (username = email)."""
    return _handle_login(db, form.username, form.password)


@router.post("/logout")
def logout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.user,
        entity_id=current_user.id,
        action=ActivityAction.user_logged_out,
        new_value=current_user.email,
    )
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=CurrentUserRead)
def read_current_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    token_payload: TokenPayload = Depends(get_token_payload),
):
    return _build_current_user_read(db, current_user, token_payload)


@router.get("/me/profile", response_model=UserProfileRead)
def read_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.user_profile_service import get_user_profile

    return get_user_profile(db, current_user)


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.new_password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password and confirmation do not match.",
        )
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    if verify_password(body.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be different from your current password.",
        )
    current_user.password_hash = hash_password(body.new_password)
    current_user.must_change_password = False
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.user,
        entity_id=current_user.id,
        action=ActivityAction.password_changed,
        new_value=current_user.email,
    )
    return ChangePasswordResponse(
        message="Password updated successfully.",
        must_change_password=False,
    )


@router.post("/impersonate/{user_id}", response_model=Token)
def impersonate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("Admin")),
):
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot impersonate themselves.",
        )
    target = user_crud.get(db, user_id)
    if target is None or not target.is_active or target.is_archived or target.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not available for impersonation.",
        )
    log_activity(
        db,
        user=admin,
        entity_type=EntityType.user,
        entity_id=target.id,
        action=ActivityAction.admin_impersonation_started,
        new_value=target.email,
    )
    return _issue_token(db, target, impersonator_id=admin.id)


@router.post("/stop-impersonation", response_model=Token)
def stop_impersonation(
    db: Session = Depends(get_db),
    token_payload: TokenPayload = Depends(get_token_payload),
):
    if token_payload.impersonator_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not currently impersonating a user.",
        )
    admin = db.get(User, token_payload.impersonator_id)
    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator session is no longer valid.",
        )
    impersonated = db.get(User, token_payload.sub)
    log_activity(
        db,
        user=admin,
        entity_type=EntityType.user,
        entity_id=token_payload.sub,
        action=ActivityAction.admin_impersonation_stopped,
        new_value=impersonated.email if impersonated is not None else str(token_payload.sub),
    )
    return _issue_token(db, admin)
