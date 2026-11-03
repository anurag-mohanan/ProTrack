"""Who may see which part of management reporting, resolved once per request.

Project figures follow the caller's project visibility and report team scope (as every other
project report does). Finance figures need Finance view access; workforce figures need Resource
Planning or HR view access; strategy changes need the strategy special permissions.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.access_control import (
    MODULE_FINANCIAL_PLANNING,
    MODULE_HUMAN_RESOURCES,
    SPECIAL_APPROVE_STRATEGY,
    SPECIAL_EXPORT_REPORTS,
    SPECIAL_MANAGE_STRATEGY,
)
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import can_view_reports, get_role_name, is_admin, user_holds_special
from app.core.team_access import project_visibility_clause
from app.models.models import Project, User
from app.services.reporting.report_scope import ReportScopeForbidden, resolve_report_scope
from app.services.skills.access import can_view_capacity


class ManagementForbidden(Exception):
    """The caller may not read or change this part of management reporting."""


@dataclass
class ManagementAccess:
    user: User
    admin: bool
    org_wide: bool
    report_team_ids: frozenset[UUID] | None
    visibility_clause: object | None
    finance: bool
    capacity: bool
    hr: bool
    manage: bool
    approve: bool
    export: bool

    @property
    def workforce(self) -> bool:
        return self.capacity or self.hr

    @property
    def reviews(self) -> bool:
        """Management reviews are company-wide documents."""
        return self.org_wide or self.manage

    def flags(self) -> dict:
        return {
            "finance": self.finance,
            "workforce": self.workforce,
            "capacity": self.capacity,
            "hr": self.hr,
            "org_wide": self.org_wide,
            "manage_strategy": self.manage,
            "approve_strategy": self.approve,
            "export": self.export,
            "reviews": self.reviews,
        }


def resolve_access(db: Session, user: User) -> ManagementAccess:
    if not can_view_reports(db, user):
        raise ManagementForbidden("Management reporting requires the Reports module.")
    try:
        report_teams = resolve_report_scope(db, user).team_ids
    except ReportScopeForbidden as exc:
        raise ManagementForbidden(str(exc)) from exc
    clause = project_visibility_clause(db, user)
    if report_teams is not None:
        team_clause = Project.team_id.in_(report_teams) if report_teams else Project.id.is_(None)
        clause = team_clause if clause is None else and_(clause, team_clause)
    role = get_role_name(db, user)
    admin = is_admin(db, user)
    approve = admin or user_holds_special(db, user, SPECIAL_APPROVE_STRATEGY)
    return ManagementAccess(
        user=user,
        admin=admin,
        org_wide=report_teams is None and clause is None,
        report_team_ids=report_teams,
        visibility_clause=clause,
        finance=user_has_module_action(user, role, MODULE_FINANCIAL_PLANNING, MODULE_ACTION_VIEW),
        capacity=can_view_capacity(db, user),
        hr=user_has_module_action(user, role, MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW),
        manage=approve or user_holds_special(db, user, SPECIAL_MANAGE_STRATEGY),
        approve=approve,
        export=user_holds_special(db, user, SPECIAL_EXPORT_REPORTS),
    )
