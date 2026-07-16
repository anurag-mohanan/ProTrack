"""Performance review defaults, rating scale, and scoring helpers."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import PLANNING_BOARD, get_role_name, is_admin
from app.models.enums import TeamRelationshipType
from app.models.models import PerformanceReviewItem, PerformanceReviewSection, PerformanceReviewSheet, Team, TeamMember, User

RATING_NA_VALUE = Decimal("0")

RATING_SCALE: list[dict[str, Any]] = [
    {
        "value": 5,
        "label": "Excellent",
        "short_label": "5",
        "guidance": "Best for business — you deserve to be followed by everyone.",
        "tone": "success",
    },
    {
        "value": 4,
        "label": "Good",
        "short_label": "4",
        "guidance": "Good, but always try to achieve the magic number 5.",
        "tone": "info",
    },
    {
        "value": 3,
        "label": "Satisfactory",
        "short_label": "3",
        "guidance": "This is good, but not the best.",
        "tone": "primary",
    },
    {
        "value": 2,
        "label": "Fair",
        "short_label": "2",
        "guidance": "Try to focus in this field and try to improve.",
        "tone": "warning",
    },
    {
        "value": 1,
        "label": "Poor",
        "short_label": "1",
        "guidance": "Sit with supervisor to understand areas to improve.",
        "tone": "error",
    },
    {
        "value": 0,
        "label": "N/A",
        "short_label": "N/A",
        "guidance": "Not applicable for this employee or review period.",
        "tone": "neutral",
    },
]

PP_HRD_FO_20_TEMPLATE: list[dict[str, Any]] = [
    {
        "title": "Core Competencies",
        "description": "Behavioural and delivery competencies assessed for the review year.",
        "employee_notes_label": "Projects done / Achievements in reviewing year",
        "items": [
            {
                "prompt": "Productivity / speed",
                "guidance": "Meeting deadlines.",
            },
            {
                "prompt": "Quality",
                "guidance": "Following standard processes, delivering without markups.",
            },
            {
                "prompt": "Initiative",
                "guidance": "Starting new things, ideas, and presenting them to leaders.",
            },
            {
                "prompt": "Communication",
                "guidance": "Communication with team members, leaders, and customers.",
            },
            {
                "prompt": "Punctuality",
                "guidance": (
                    "Time keeping — coming to office, arriving early when needed, "
                    "and staying late when needed."
                ),
            },
            {
                "prompt": "Problem solving",
                "guidance": (
                    "Self decision quality and accuracy — can the employee take the "
                    "right decision in most cases?"
                ),
            },
            {
                "prompt": "Leadership",
                "guidance": (
                    "Leading the team, solving doubts, and helping with issues."
                ),
            },
            {
                "prompt": "Dependability",
                "guidance": "How much the supervisor can depend on the employee.",
            },
            {
                "prompt": "Training",
                "guidance": "Getting trained and training others.",
            },
        ],
    },
    {
        "title": "Technical Competencies",
        "description": "Role-specific technical skills and tooling proficiency.",
        "employee_notes_label": "Targets / Goals for upcoming year",
        "items": [
            {"prompt": "Design", "guidance": "Design execution quality and ownership."},
            {"prompt": "Surfacing", "guidance": "Surfacing quality, speed, and finish."},
            {
                "prompt": "Office tools (excel, ppt, word)",
                "guidance": "Proficiency with office productivity tools.",
            },
            {"prompt": "Customization", "guidance": "Customization work quality and speed."},
            {
                "prompt": "Subtasks (Prints, Plaques)",
                "guidance": "Execution of supporting subtasks such as prints and plaques.",
            },
            {
                "prompt": "Overall CAD Software speed (NX/Solidworks)",
                "guidance": "Speed and accuracy across primary CAD platforms.",
            },
            {"prompt": "Estimation", "guidance": "Estimation accuracy and turnaround."},
        ],
    },
]

DEFAULT_REVIEW_TEMPLATE = PP_HRD_FO_20_TEMPLATE


def rating_label(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = int(value)
    for row in RATING_SCALE:
        if row["value"] == normalized:
            return str(row["label"])
    return None


def section_average_score(section: PerformanceReviewSection) -> Decimal | None:
    ratings = [
        item.rating
        for item in section.items
        if item.rating is not None and item.rating > RATING_NA_VALUE
    ]
    if not ratings:
        return None
    total = sum(ratings, start=Decimal("0"))
    return (total / Decimal(len(ratings))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def sheet_overall_score(sheet: PerformanceReviewSheet) -> Decimal | None:
    ratings: list[Decimal] = []
    for section in sheet.sections:
        for item in section.items:
            if item.rating is not None and item.rating > RATING_NA_VALUE:
                ratings.append(item.rating)
    if not ratings:
        return None
    total = sum(ratings, start=Decimal("0"))
    return (total / Decimal(len(ratings))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def sheet_completion_ratio(sheet: PerformanceReviewSheet) -> tuple[int, int]:
    total = sum(len(section.items) for section in sheet.sections)
    rated = sum(
        1
        for section in sheet.sections
        for item in section.items
        if item.rating is not None
    )
    return rated, total


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
