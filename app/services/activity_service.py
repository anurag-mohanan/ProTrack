import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import ActivityAction, EntityType
from app.models.models import Activity, User


def log_activity(
    db: Session,
    *,
    user: User | None,
    entity_type: EntityType,
    entity_id: UUID,
    action: ActivityAction,
    old_value: object | None = None,
    new_value: object | None = None,
) -> Activity:
    activity = Activity(
        user_id=user.id if user is not None else None,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_value=_serialize_value(old_value),
        new_value=_serialize_value(new_value),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def _serialize_value(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "value"):
        return str(value.value)
    return json.dumps(value, default=str)
