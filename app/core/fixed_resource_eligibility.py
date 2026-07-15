"""Who counts as customer-paid fixed / retainer resource headcount."""

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
    get_role_name,
    normalize_role_name,
)
from app.db.phase23_finance_team_scope_schema_sync import CORPORATE_TEAM_NAME
from app.models.models import Team, User

# Delivery engineering roles billed to customers under retainer / fixed resource math.
FIXED_RESOURCE_ROLE_DEFAULTS = frozenset(
    {
        SENIOR_DESIGNER,
        DESIGNER,
        JUNIOR_DESIGNER,
        SURFACER,
    }
)

# Management / HQ / compliance — Prosohm overhead, not customer-paid headcount.
MANAGEMENT_OVERHEAD_ROLE_DEFAULTS = frozenset(
    {
        ADMIN,
        OFFICE_ADMINISTRATOR,
        PLANNING_BOARD,
        DESIGN_LEADER,
        ENGINEERING_MANAGER,
        HR,
        READ_ONLY,
        "Project Manager",
    }
)


def role_is_fixed_resource_default(role_name: str) -> bool:
    return normalize_role_name(role_name) in FIXED_RESOURCE_ROLE_DEFAULTS


def role_is_management_overhead_default(role_name: str) -> bool:
    return normalize_role_name(role_name) in MANAGEMENT_OVERHEAD_ROLE_DEFAULTS


def default_is_billable_headcount(
    *,
    team: Team | None,
    role_name: str | None,
) -> bool:
    """Default for new memberships: designers/surfacer on delivery teams only."""
    if team is not None and team.name == CORPORATE_TEAM_NAME:
        return False
    if not role_name:
        return False
    return role_is_fixed_resource_default(role_name)


def default_is_billable_headcount_for_user(
    db: Session,
    *,
    team: Team | None,
    user: User | None,
) -> bool:
    if user is None:
        return False
    return default_is_billable_headcount(team=team, role_name=get_role_name(db, user))
