"""Employee vs virtual/system accounts.

Virtual users (shared mailboxes, kiosks, integrations, test logins) keep their
role and permissions but are not people: they are left out of HR headcount,
shift rosters, IT asset allocation, timesheet compliance and capacity.
"""

from __future__ import annotations

from sqlalchemy import or_

from app.models.enums import UserType
from app.models.models import User


def is_virtual_user(user: User | None) -> bool:
    return user is not None and getattr(user, "user_type", None) == UserType.virtual


def employee_user_clause():
    """SQL filter selecting real employees (NULL counts as employee for legacy rows)."""
    return or_(User.user_type == UserType.employee, User.user_type.is_(None))


VIRTUAL_USER_EXCLUDED_MESSAGE = (
    "{name} is a virtual/system account and cannot be used for {purpose}."
)
