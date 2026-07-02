from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.crud.preferences import get_or_create_user_preferences, update_user_preferences
from app.models.models import User
from app.schemas.preferences import UserPreferencesRead, UserPreferencesUpdate

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("/me", response_model=UserPreferencesRead)
def read_my_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_or_create_user_preferences(db, current_user)


@router.patch("/me", response_model=UserPreferencesRead)
def update_my_preferences(
    payload: UserPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_user_preferences(db, current_user, payload)
