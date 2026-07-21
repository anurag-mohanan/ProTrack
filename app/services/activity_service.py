import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.request_context import get_client_ip, get_user_agent
from app.models.enums import ActivityAction, EntityType
from app.models.models import Activity, User

OUTCOME_SUCCESS = "success"
OUTCOME_FAILURE = "failure"


def log_activity(
    db: Session,
    *,
    user: User | None,
    entity_type: EntityType,
    entity_id: UUID,
    action: ActivityAction,
    old_value: object | None = None,
    new_value: object | None = None,
    outcome: str | None = None,
    module: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    commit: bool = True,
) -> Activity:
    activity = Activity(
        user_id=user.id if user is not None else None,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_value=_serialize_value(old_value),
        new_value=_serialize_value(new_value),
        outcome=outcome,
        module=(module or None),
        ip_address=(ip_address if ip_address is not None else get_client_ip()),
        user_agent=(user_agent if user_agent is not None else get_user_agent()),
    )
    db.add(activity)
    if commit:
        db.commit()
        db.refresh(activity)
    else:
        db.flush()
    return activity


def _serialize_value(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "value"):
        return str(value.value)
    return json.dumps(value, default=str)
