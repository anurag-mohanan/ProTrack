"""Performance review defaults, rating scale, scoring, and project discovery."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import PLANNING_BOARD, get_role_name, is_admin
from app.models.enums import TeamRelationshipType
from app.models.models import (
    Milestone,
    PerformanceReviewItem,
    PerformanceReviewProject,
    PerformanceReviewSection,
    PerformanceReviewSheet,
    Project,
    Team,
    TeamMember,
    Timesheet,
    TimesheetEntry,
    User,
)

REVIEW_CYCLE_MONTH = 7
FORM_CODE = "PP-HRD-FO-20"
FORM_TITLE = "Employee Performance Review"
FORM_REVISION = "Rev 3 · 01/19/2023"

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
        "description": (
            "Role-specific technical skills and tooling proficiency. "
            "Use N/A for competencies outside the employee's function "
            "(e.g. sales, HR, finance, or administration roles)."
        ),
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


def current_review_year(as_of: date | None = None) -> int:
    today = as_of or date.today()
    return today.year if today.month >= REVIEW_CYCLE_MONTH else today.year


def review_period_bounds(review_year: int | None = None, as_of: date | None = None) -> tuple[date, date]:
    year = review_year or current_review_year(as_of)
    return date(year - 1, REVIEW_CYCLE_MONTH, 1), date(year, REVIEW_CYCLE_MONTH - 1, 30)


def default_period_label(review_year: int | None = None, as_of: date | None = None) -> str:
    year = review_year or current_review_year(as_of)
    return f"FY {year - 1}-{str(year)[-2:]}"


def _project_role_label(project: Project, user_id: UUID) -> str | None:
    if project.design_leader_id == user_id:
        return "Design Leader"
    if project.designer_id == user_id:
        return "Designer"
    if project.surfacer_id == user_id:
        return "Surfacer"
    return None


def discover_employee_projects(
    db: Session,
    employee_id: UUID,
    *,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    """Suggest projects completed or contributed to during the annual review window."""
    discovered: dict[UUID, dict[str, Any]] = {}

    direct_projects = db.scalars(
        select(Project)
        .options(selectinload(Project.customer))
        .where(
            Project.is_deleted.is_(False),
            or_(
                Project.design_leader_id == employee_id,
                Project.designer_id == employee_id,
                Project.surfacer_id == employee_id,
            ),
        )
    ).all()
    for project in direct_projects:
        role = _project_role_label(project, employee_id)
        discovered[project.id] = {
            "project_id": project.id,
            "tool_number": project.tool_number,
            "part_description": project.part_description,
            "customer_name": project.customer.name if project.customer is not None else None,
            "assignment_role": role,
            "hours_logged": Decimal("0"),
            "execution_status": project.execution_status.value if project.execution_status else None,
            "project_stage": project.project_stage.value if project.project_stage else None,
            "completed_at": project.completed_at.date() if project.completed_at else None,
            "sources": {"assignment"},
        }

    milestone_rows = db.execute(
        select(Milestone.project_id, func.count(Milestone.id))
        .where(Milestone.assigned_user_id == employee_id)
        .group_by(Milestone.project_id)
    ).all()
    for project_id, milestone_count in milestone_rows:
        project = db.scalar(
            select(Project).options(selectinload(Project.customer)).where(Project.id == project_id)
        )
        if project is None or project.is_deleted:
            continue
        row = discovered.setdefault(
            project_id,
            {
                "project_id": project.id,
                "tool_number": project.tool_number,
                "part_description": project.part_description,
                "customer_name": project.customer.name if project.customer is not None else None,
                "assignment_role": "Milestone assignee",
                "hours_logged": Decimal("0"),
                "execution_status": project.execution_status.value if project.execution_status else None,
                "project_stage": project.project_stage.value if project.project_stage else None,
                "completed_at": project.completed_at.date() if project.completed_at else None,
                "sources": set(),
            },
        )
        row["sources"].add("milestone")
        if milestone_count and row.get("assignment_role") in (None, "Milestone assignee"):
            row["assignment_role"] = f"Milestone assignee ({int(milestone_count)})"

    timesheet_rows = db.execute(
        select(
            TimesheetEntry.project_id,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
            func.min(TimesheetEntry.entry_date),
            func.max(TimesheetEntry.entry_date),
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Timesheet.user_id == employee_id,
            TimesheetEntry.project_id.is_not(None),
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.entry_date >= period_start,
            TimesheetEntry.entry_date <= period_end,
        )
        .group_by(TimesheetEntry.project_id)
    ).all()

    for project_id, hours, first_entry, last_entry in timesheet_rows:
        if project_id is None:
            continue
        project = db.scalar(
            select(Project).options(selectinload(Project.customer)).where(Project.id == project_id)
        )
        if project is None or project.is_deleted:
            continue
        hours_decimal = Decimal(str(hours or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if project_id in discovered:
            row = discovered[project_id]
            row["hours_logged"] = hours_decimal
            row["sources"].add("timesheet")
            if row.get("assignment_role") is None:
                row["assignment_role"] = "Contributor"
        else:
            discovered[project_id] = {
                "project_id": project.id,
                "tool_number": project.tool_number,
                "part_description": project.part_description,
                "customer_name": project.customer.name if project.customer is not None else None,
                "assignment_role": "Contributor",
                "hours_logged": hours_decimal,
                "execution_status": project.execution_status.value if project.execution_status else None,
                "project_stage": project.project_stage.value if project.project_stage else None,
                "completed_at": project.completed_at.date() if project.completed_at else None,
                "sources": {"timesheet"},
            }

    results: list[dict[str, Any]] = []
    for index, row in enumerate(
        sorted(
            discovered.values(),
            key=lambda item: (
                -(float(item.get("hours_logged") or 0)),
                item.get("tool_number") or "",
            ),
        )
    ):
        hours = row.get("hours_logged") or Decimal("0")
        completed_at = row.get("completed_at")
        in_period = bool(hours > 0)
        if not in_period and completed_at is not None:
            in_period = period_start <= completed_at <= period_end
        if not in_period:
            continue
        sources = row.pop("sources", set())
        source_label = ", ".join(sorted(sources)) if sources else "platform"
        contribution = (
            f"Auto-imported from ProTrack ({source_label}). "
            f"Logged {row.get('hours_logged') or 0}h between "
            f"{period_start.isoformat()} and {period_end.isoformat()}."
        )
        results.append(
            {
                **row,
                "contribution_summary": contribution,
                "achievement_notes": None,
                "is_auto_imported": True,
                "sort_order": index,
            }
        )
    return results


def seed_review_projects(
    sheet: PerformanceReviewSheet,
    db: Session,
    *,
    period_start: date,
    period_end: date,
) -> None:
    suggestions = discover_employee_projects(
        db,
        sheet.employee_id,
        period_start=period_start,
        period_end=period_end,
    )
    for row in suggestions:
        sheet.projects.append(
            PerformanceReviewProject(
                project_id=row.get("project_id"),
                tool_number=str(row.get("tool_number") or ""),
                part_description=row.get("part_description"),
                customer_name=row.get("customer_name"),
                assignment_role=row.get("assignment_role"),
                hours_logged=row.get("hours_logged"),
                execution_status=row.get("execution_status"),
                project_stage=row.get("project_stage"),
                completed_at=row.get("completed_at"),
                contribution_summary=row.get("contribution_summary"),
                achievement_notes=row.get("achievement_notes"),
                is_auto_imported=bool(row.get("is_auto_imported")),
                sort_order=int(row.get("sort_order") or 0),
            )
        )


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
