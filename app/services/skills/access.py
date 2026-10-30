"""Who may see, declare, assess and configure engineering skills.

Built only from existing rules:

* Assessing a person's skills follows ``user_can_manage_team_reviews`` (the rule
  that already governs editing the Performance team skill matrix): admins, HR,
  Office Administrator everywhere; team leads, team leaders,
  engineering managers and reviewers for their teams; Performance editors for
  their accessible teams.
* Viewing other people's skill profiles is allowed to assessors, to Human
  Resources viewers and to resource planners, each within their team scope
  (``get_accessible_team_ids``).
* Everyone may view and declare their own skills. Nobody assesses their own.
* Taxonomy and proficiency framework: admins and Human Resources ``configure``.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_control import (
    MODULE_HUMAN_RESOURCES,
    MODULE_PERFORMANCE,
    MODULE_RESOURCE_PLANNING,
    SPECIAL_VIEW_RESOURCE_PLANNING,
    normalize_role_name,
    user_has_module,
    user_has_special,
)
from app.core.module_actions import (
    MODULE_ACTION_CONFIGURE,
    MODULE_ACTION_CREATE,
    MODULE_ACTION_EDIT,
    MODULE_ACTION_EDIT_REVIEWS,
    MODULE_ACTION_VIEW,
    user_has_module_action,
)
from app.core.permissions import can_view_resource_planning, get_role_name, is_admin
from app.core.team_access import get_accessible_team_ids, team_member_user_ids
from app.models.enums import TeamRelationshipType
from app.models.models import Team, TeamMember, User
from app.services.user_team_service import get_user_team_ids

# Planning Board can edit the Performance matrix but is a shared wall-monitor
# login; a verified skill needs an accountable reviewer, so it only gets view.
ORG_WIDE_REVIEW_ROLES = {"HR", "Office Administrator"}

TeamScope = set[UUID] | None  # None = every team


def can_view_capacity(db: Session, user: User) -> bool:
    """Resource Planning roles, module or the view_resource_planning special permission."""
    if can_view_resource_planning(db, user):
        return True
    role = normalize_role_name(get_role_name(db, user))
    return user_has_module(user, role, MODULE_RESOURCE_PLANNING) or user_has_special(
        user, role, SPECIAL_VIEW_RESOURCE_PLANNING
    )


def _union(a: TeamScope, b: TeamScope) -> TeamScope:
    if a is None or b is None:
        return None
    return a | b


def _review_team_ids(db: Session, user: User, role_name: str | None) -> TeamScope:
    if is_admin(db, user) or role_name in ORG_WIDE_REVIEW_ROLES:
        return None
    teams: set[UUID] = set(
        db.scalars(select(Team.id).where(Team.team_lead_id == user.id, Team.is_active.is_(True))).all()
    )
    teams.update(
        db.scalars(
            select(TeamMember.team_id).where(
                TeamMember.user_id == user.id,
                TeamMember.relationship_type.in_(
                    (
                        TeamRelationshipType.team_leader,
                        TeamRelationshipType.engineering_manager,
                        TeamRelationshipType.reviewer,
                    )
                ),
            )
        ).all()
    )
    if any(
        user_has_module_action(user, role_name, MODULE_PERFORMANCE, action)
        for action in (MODULE_ACTION_EDIT, MODULE_ACTION_EDIT_REVIEWS, MODULE_ACTION_CREATE)
    ):
        accessible = get_accessible_team_ids(db, user)
        if accessible is None:
            return None
        teams |= accessible
    return teams


@dataclass
class SkillAccess:
    user: User
    is_admin: bool
    can_manage_taxonomy: bool
    review_team_ids: TeamScope
    view_team_ids: TeamScope
    can_match_resources: bool

    @property
    def can_review_anyone(self) -> bool:
        return self.review_team_ids is None or bool(self.review_team_ids)

    @property
    def can_view_others(self) -> bool:
        return self.view_team_ids is None or bool(self.view_team_ids)

    @staticmethod
    def _in_scope(scope: TeamScope, subject_teams: set[UUID]) -> bool:
        return scope is None or bool(scope & subject_teams)

    def can_view_profile(self, db: Session, subject_id: UUID) -> bool:
        if subject_id == self.user.id:
            return True
        return self.can_view_others and self._in_scope(self.view_team_ids, get_user_team_ids(db, subject_id))

    def can_review(self, db: Session, subject_id: UUID) -> bool:
        if subject_id == self.user.id or not self.can_review_anyone:
            return False
        return self._in_scope(self.review_team_ids, get_user_team_ids(db, subject_id))

    def visible_user_ids(self, db: Session, team_ids: set[UUID] | None = None) -> set[UUID] | None:
        """Users whose profiles the caller may view, optionally narrowed to ``team_ids``. None = everyone."""
        scope = self.view_team_ids
        if team_ids is not None:
            scope = set(team_ids) if scope is None else scope & set(team_ids)
        if scope is None:
            return None
        ids = team_member_user_ids(db, list(scope)) if scope else set()
        if team_ids is None:
            ids.add(self.user.id)
        return ids

    def reviewable_user_ids(self, db: Session) -> set[UUID] | None:
        if self.review_team_ids is None:
            return None
        ids = team_member_user_ids(db, list(self.review_team_ids)) if self.review_team_ids else set()
        ids.discard(self.user.id)
        return ids


def resolve_skill_access(db: Session, user: User) -> SkillAccess:
    role_name = get_role_name(db, user)
    admin = is_admin(db, user)
    review = _review_team_ids(db, user, role_name)
    view = review
    can_match = can_view_capacity(db, user)
    if user_has_module_action(user, role_name, MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW) or can_match:
        accessible = get_accessible_team_ids(db, user)
        view = _union(view, accessible)
    return SkillAccess(
        user=user,
        is_admin=admin,
        can_manage_taxonomy=admin
        or user_has_module_action(user, role_name, MODULE_HUMAN_RESOURCES, MODULE_ACTION_CONFIGURE),
        review_team_ids=review,
        view_team_ids=view,
        can_match_resources=can_match,
    )
