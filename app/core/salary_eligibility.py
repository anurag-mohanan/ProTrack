"""Who must have a People costs / salary profile."""

from __future__ import annotations

from app.core.permissions import ADMIN, PLANNING_BOARD, normalize_role_name
from app.models.models import User

# Non-headcount / virtual accounts — salary not required by default.
SALARY_EXEMPT_ROLE_DEFAULTS = frozenset({ADMIN, PLANNING_BOARD})


def default_requires_salary_for_role(role_name: str) -> bool:
    return normalize_role_name(role_name) not in SALARY_EXEMPT_ROLE_DEFAULTS


def user_requires_salary(user: User) -> bool:
    """Per-user flag (role default at create; admin may override)."""
    return bool(getattr(user, "requires_salary", True))
