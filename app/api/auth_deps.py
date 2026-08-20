from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.auth import decode_access_token
from app.core.module_actions import user_has_module_action
from app.core.permissions import get_role_name, normalize_role_name, user_holds_special
from app.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: UUID = payload.sub
    except InvalidTokenError as exc:
        raise credentials_exception from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active or user.is_archived or user.is_deleted:
        raise credentials_exception

    # Stateless force-logout / session revocation: tokens issued before a
    # token_version bump are rejected. Legacy tokens (tv=0) match the default.
    if int(getattr(user, "token_version", 0) or 0) != int(payload.token_version or 0):
        raise credentials_exception

    # Idle / max-session-age timeout based on the token issued-at claim. The
    # /auth/refresh endpoint mints a fresh token to keep active users signed in.
    from app.services.security_policy_service import get_effective_policy

    idle_minutes = get_effective_policy(db).session_idle_timeout_minutes
    if idle_minutes > 0 and payload.issued_at is not None:
        issued = payload.issued_at
        if issued.tzinfo is None:
            issued = issued.replace(tzinfo=UTC)
        if datetime.now(UTC) - issued > timedelta(minutes=idle_minutes):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired due to inactivity. Please sign in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    request.state.user = user
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        role_name = normalize_role_name(get_role_name(db, current_user))
        normalized_allowed = {normalize_role_name(role) for role in roles}
        if role_name not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


def require_module_action(module: str, action: str) -> Callable[..., User]:
    """Guard requiring the user to hold ``action`` on ``module``.

    Enforces enterprise action-based RBAC (view/create/edit/delete/approve/
    export/import/configure) uniformly at the API edge.
    """

    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        role_name = normalize_role_name(get_role_name(db, current_user))
        if not user_has_module_action(current_user, role_name, module, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{action}' permission on '{module}'.",
            )
        return current_user

    return dependency


def require_special(permission: str) -> Callable[..., User]:
    """Guard requiring the user to hold a specific special permission."""

    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not user_holds_special(db, current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires the '{permission}' permission.",
            )
        return current_user

    return dependency
