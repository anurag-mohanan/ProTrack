import json

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.foundation import UserPreferences
from app.models.models import User
from app.schemas.preferences import UserPreferencesUpdate

_VALID_PORTFOLIO_SCOPES = frozenset({"my_streams", "my_teams", "all"})
_VALID_CC_LAYOUTS = frozenset({"list", "card", "grouped"})
_VALID_SIDEBAR_SECTIONS = frozenset(
    {"engineering", "operations", "hr", "it", "future", "admin"}
)


def get_or_create_user_preferences(db: Session, user: User) -> UserPreferences:
    if user.preferences is not None:
        return user.preferences
    existing = db.scalar(select(UserPreferences).where(UserPreferences.user_id == user.id))
    if existing is not None:
        return existing
    prefs = UserPreferences(user_id=user.id)
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return prefs


def update_user_preferences(
    db: Session, user: User, payload: UserPreferencesUpdate
) -> UserPreferences:
    prefs = get_or_create_user_preferences(db, user)
    data = payload.model_dump(exclude_unset=True)
    scope = data.get("projects_portfolio_scope")
    if scope is not None and scope not in _VALID_PORTFOLIO_SCOPES:
        raise ProTrackValidationError(
            "projects_portfolio_scope must be one of: my_streams, my_teams, all"
        )
    layout = data.get("projects_cc_layout")
    if layout is not None and layout not in _VALID_CC_LAYOUTS:
        raise ProTrackValidationError(
            "projects_cc_layout must be one of: list, card, grouped"
        )
    if "sidebar_section_state" in data and data["sidebar_section_state"] is not None:
        raw = data["sidebar_section_state"]
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as exc:
            raise ProTrackValidationError(
                "sidebar_section_state must be a JSON object of section→bool"
            ) from exc
        if not isinstance(parsed, dict):
            raise ProTrackValidationError(
                "sidebar_section_state must be a JSON object of section→bool"
            )
        cleaned: dict[str, bool] = {}
        for key, value in parsed.items():
            if key not in _VALID_SIDEBAR_SECTIONS:
                continue
            cleaned[key] = bool(value)
        data["sidebar_section_state"] = json.dumps(cleaned)
    for key, value in data.items():
        setattr(prefs, key, value)
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return prefs
