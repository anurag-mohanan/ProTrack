"""The signed-in user's permissions, resolved once per turn with the existing rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.access_control import MODULE_FINANCIAL_PLANNING
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import can_view_reports, get_role_name, is_admin
from app.core.team_access import project_visibility_clause, resolve_team_scope
from app.models.models import User
from app.services.reporting.report_scope import ReportScopeForbidden, resolve_report_scope
from app.services.skills.access import SkillAccess, can_view_capacity, resolve_skill_access


@dataclass
class AssistantContext:
    db: Session
    user: User
    today: date
    is_admin: bool
    visibility_clause: object | None
    can_view_reports: bool
    report_team_ids: frozenset[UUID] | None
    finance_visible: bool
    can_view_capacity: bool
    capacity_team_ids: set[UUID] | None
    skill_access: SkillAccess
    # Source ids returned by tools during this turn; recommendations must cite them.
    seen_sources: dict[str, dict] = field(default_factory=dict)
    seen_project_ids: set[UUID] = field(default_factory=set)
    conversation_id: UUID | None = None
    created_recommendation_ids: list[UUID] = field(default_factory=list)


def build_context(db: Session, user: User, *, today: date | None = None) -> AssistantContext:
    reports = can_view_reports(db, user)
    report_team_ids: frozenset[UUID] | None = frozenset()
    if reports:
        try:
            report_team_ids = resolve_report_scope(db, user).team_ids
        except ReportScopeForbidden:
            reports = False
    capacity = can_view_capacity(db, user)
    return AssistantContext(
        db=db,
        user=user,
        today=today or date.today(),
        is_admin=is_admin(db, user),
        visibility_clause=project_visibility_clause(db, user),
        can_view_reports=reports,
        report_team_ids=report_team_ids,
        finance_visible=user_has_module_action(
            user, get_role_name(db, user), MODULE_FINANCIAL_PLANNING, MODULE_ACTION_VIEW
        ),
        can_view_capacity=capacity,
        capacity_team_ids=resolve_team_scope(db, user) if capacity else set(),
        skill_access=resolve_skill_access(db, user),
    )
