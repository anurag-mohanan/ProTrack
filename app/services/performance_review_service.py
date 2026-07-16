"""Performance review defaults and access checks."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import PLANNING_BOARD, get_role_name, is_admin
from app.models.enums import TeamRelationshipType
from app.models.models import PerformanceReviewSheet, Team, TeamMember, User

DEFAULT_REVIEW_TEMPLATE: list[dict[str, Any]] = [
    {
        "title": "Role delivery",
        "description": "Quality, ownership, execution, and reliability in day-to-day work.",
        "items": [
            "Delivers committed work with the expected quality level.",
            "Owns timelines, escalations, and follow-through.",
            "Applies engineering/process discipline consistently.",
        ],
    },
    {
        "title": "Collaboration and behavior",
        "description": "Team contribution, communication, and culture fit.",
        "items": [
            "Communicates clearly with peers and stakeholders.",
            "Supports team members and contributes positively to culture.",
            "Responds well to feedback and incorporates learning.",
        ],
    },
    {
        "title": "Growth and future readiness",
        "description": "Capability development and next-cycle focus.",
        "items": [
            "Demonstrates growth in technical or functional capability.",
            "Shows initiative to improve processes or efficiency.",
            "Has a clear development focus for the next review period.",
        ],
    },
]


def user_can_manage_team_reviews(db: Session, user: User, team_id: UUID) -> bool:
    if is_admin(db, user):
        return True
    role_name = get_role_name(db, user)
    if role_name == PLANNING_BOARD:
        return True
    team = db.get(Team, team_id)
    if team is not None and team.team_lead_id == user.id:
        return True
    relationship = db.scalar(
        select(TeamMember.id).where(
            TeamMember.user_id == user.id,
            TeamMember.team_id == team_id,
            TeamMember.relationship_type.in_(
                (
                    TeamRelationshipType.team_leader,
                    TeamRelationshipType.engineering_manager,
                    TeamRelationshipType.reviewer,
                )
            ),
        )
    )
    if relationship is not None:
        return True
    if role_name in {"HR", "Office Administrator"}:
        return True
    return False


def user_can_view_review(db: Session, user: User, sheet: PerformanceReviewSheet) -> bool:
    if sheet.employee_id == user.id or sheet.reviewer_id == user.id:
        return True
    if sheet.team_id is not None and user_can_manage_team_reviews(db, user, sheet.team_id):
        return True
    return False
