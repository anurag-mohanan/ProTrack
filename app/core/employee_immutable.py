"""Historical employee facts: lock after first value, correct only via dedicated API."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.exceptions import ProTrackValidationError
from app.models.models import User

# Fields that must not change through the normal user PATCH once a value exists.
IMMUTABLE_USER_FIELDS: tuple[str, ...] = ("joining_date", "first_job_date")

CORRECTION_HINT = (
    "Use POST /api/v1/users/{id}/historical-corrections with a reason "
    "to correct historical employment dates."
)


def _dates_equal(left: date | None, right: Any) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    if isinstance(right, str):
        return left.isoformat() == right[:10]
    return left == right


def reject_immutable_user_mutations(user: User, payload: dict[str, Any]) -> dict[str, Any]:
    """Drop no-op immutable fields; raise if an established value would change."""
    cleaned = dict(payload)
    blocked: list[str] = []
    for field in IMMUTABLE_USER_FIELDS:
        if field not in cleaned:
            continue
        incoming = cleaned[field]
        current = getattr(user, field, None)
        if current is None:
            continue
        if _dates_equal(current, incoming):
            cleaned.pop(field, None)
            continue
        blocked.append(field)
        cleaned.pop(field, None)
    if blocked:
        labels = ", ".join(blocked)
        raise ProTrackValidationError(
            f"{labels} cannot be changed on a normal save. {CORRECTION_HINT}"
        )
    return cleaned


def reject_immutable_onboarding_mutations(
    *,
    current_code: str | None,
    current_joining: date | None,
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Lock onboarding employee_code / joining_date after they are first stored."""
    cleaned = dict(fields)
    blocked: list[str] = []

    if "employee_code" in cleaned and current_code:
        incoming = cleaned.get("employee_code")
        incoming_str = (incoming or "").strip() if isinstance(incoming, str) else incoming
        if incoming_str != current_code:
            blocked.append("employee_code")
        cleaned.pop("employee_code", None)

    if "joining_date" in cleaned and current_joining is not None:
        incoming = cleaned.get("joining_date")
        if not _dates_equal(current_joining, incoming):
            blocked.append("joining_date")
        cleaned.pop("joining_date", None)

    if blocked:
        raise ProTrackValidationError(
            "Employee ID and joining date are historical facts once set. "
            "Correct them from Users → Correct historical dates (joining date) "
            "or ask an administrator; do not overwrite onboarding headers."
            if "joining_date" in blocked
            else "Employee ID cannot be changed once set."
        )
    return cleaned
