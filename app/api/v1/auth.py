from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.auth import create_access_token
from app.core.permissions import get_role_name
from app.crud.auth import authenticate_user
from app.models.enums import ActivityAction, EntityType
from app.models.models import User
from app.schemas.auth import CurrentUserRead, LoginRequest, Token
from app.services.activity_service import log_activity

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token(user: User) -> Token:
    access_token = create_access_token(user_id=user.id, email=user.email)
    return Token(access_token=access_token)


@router.post("/login", response_model=Token)
def login_json(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, email=body.email, password=body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    log_activity(
        db,
        user=user,
        entity_type=EntityType.user,
        entity_id=user.id,
        action=ActivityAction.user_logged_in,
        new_value=user.email,
    )
    return _issue_token(user)


@router.post("/token", response_model=Token)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2-compatible token endpoint for Swagger Authorize (username = email)."""
    user = authenticate_user(db, email=form.username, password=form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_token(user)


@router.get("/me", response_model=CurrentUserRead)
def read_current_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return CurrentUserRead(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role_id=current_user.role_id,
        role_name=get_role_name(db, current_user),
        is_active=current_user.is_active,
    )
