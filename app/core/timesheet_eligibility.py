"""Who must fill timesheets vs who may only monitor or is exempt."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.access_control import HR, OFFICE_ADMINISTRATOR
from app.core.permissions import (
    ADMIN,
    DESIGN_LEADER,
    DESIGNER,
    ENGINEERING_MANAGER,
    JUNIOR_DESIGNER,
    PLANNING_BOARD,
    READ_ONLY,
    SENIOR_DESIGNER,
    SURFACER,
    can_write_timesheet_entry,
    get_role_name,
    normalize_role_name,
)
from app.models.models import User

# Delivery roles always default to required (including Design Leader on Overheads).
REQUIRES_TIMESHEET_ROLE_DEFAULTS = frozenset(
    {
        DESIGN_LEADER,
        SENIOR_DESIGNER,
        DESIGNER,
        JUNIOR_DESIGNER,
        SURFACER,
    }
)

# Never get a personal entry form (monitor / wall / audit accounts).
OWN_TIMESHEET_EXEMPT_ROLES = frozenset(
    {
        ADMIN,
        READ_ONLY,
        PLANNING_BOARD,
        HR,
        OFFICE_ADMINISTRATOR,
    }
)

# Never counted as designers / capacity / utilization resources (virtual & monitor accounts).
NON_CAPACITY_RESOURCE_ROLES = OWN_TIMESHEET_EXEMPT_ROLES


def default_requires_timesheet_for_role(role_name: str) -> bool:
    return normalize_role_name(role_name) in REQUIRES_TIMESHEET_ROLE_DEFAULTS


def role_is_non_capacity_resource(role_name: str | None) -> bool:
    """True for wall monitors and other virtual accounts (e.g. Planning Board)."""
    if not role_name:
        return False
    return normalize_role_name(role_name) in NON_CAPACITY_RESOURCE_ROLES


def user_requires_timesheet(user: User) -> bool:
    """Per-user flag (role default at create; admin may override)."""
    return bool(getattr(user, "requires_timesheet", False))


def user_can_enter_own_timesheet(db: Session, user: User) -> bool:
    """Personal timesheet form / optional logging (not the same as required)."""
    role_name = normalize_role_name(get_role_name(db, user))
    if role_name in OWN_TIMESHEET_EXEMPT_ROLES:
        return False
    return can_write_timesheet_entry(db, user)


def role_is_timesheet_monitor_only(role_name: str) -> bool:
    normalized = normalize_role_name(role_name)
    return normalized in {HR, OFFICE_ADMINISTRATOR, ENGINEERING_MANAGER, ADMIN}
