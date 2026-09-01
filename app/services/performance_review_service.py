"""Performance review defaults, rating scale, scoring, and project discovery."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import PLANNING_BOARD, get_role_name, is_admin
from app.core.module_actions import (
    MODULE_ACTION_CREATE,
    MODULE_ACTION_EDIT,
    MODULE_ACTION_EDIT_REVIEWS,
    user_has_module_action,
)
from app.core.access_control import MODULE_PERFORMANCE
from app.core.team_access import get_accessible_team_ids
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

STAGE_SELF = "self"
STAGE_MANAGER = "manager"
STAGE_CALIBRATION = "calibration"
STAGE_FINAL = "final"
STAGE_ACKNOWLEDGED = "acknowledged"

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
    return today.year + 1 if today.month >= REVIEW_CYCLE_MONTH else today.year


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


def format_tenure(start: date | None, as_of: date | None = None) -> str | None:
    if start is None:
        return None
    end = as_of or date.today()
    if end < start:
        return None
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    if months < 0:
        months = 0
    years, rem = divmod(months, 12)
    if years and rem:
        return f"{years}y {rem}m"
    if years:
        return f"{years} year{'s' if years != 1 else ''}"
    return f"{rem} month{'s' if rem != 1 else ''}"


def _project_complexity(project: Project) -> str | None:
    if project.complexity is None:
        return None
    return project.complexity.value if hasattr(project.complexity, "value") else str(project.complexity)


def _owned_project_row(project: Project, employee_id: UUID, hours: Decimal | None = None) -> dict[str, Any]:
    return {
        "project_id": project.id,
        "tool_number": project.tool_number,
        "part_description": project.part_description,
        "customer_name": project.customer.name if project.customer is not None else None,
        "assignment_role": _project_role_label(project, employee_id),
        "hours_logged": hours if hours is not None else Decimal("0"),
        "execution_status": project.execution_status.value if project.execution_status else None,
        "project_stage": project.project_stage.value if project.project_stage else None,
        "completed_at": project.completed_at.date() if project.completed_at else None,
        "ownership_type": "owned",
        "tasks_summary": None,
        "complexity": _project_complexity(project),
    }


def _is_project_owner(project: Project, user_id: UUID) -> bool:
    return user_id in {
        project.design_leader_id,
        project.designer_id,
        project.surfacer_id,
    }


def _tasks_for_employee_project(
    db: Session,
    employee_id: UUID,
    project_id: UUID,
    *,
    period_start: date,
    period_end: date,
) -> str | None:
    from app.models.models import TaskType

    task_names = db.scalars(
        select(TaskType.name)
        .join(TimesheetEntry, TimesheetEntry.task_type_id == TaskType.id)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Timesheet.user_id == employee_id,
            TimesheetEntry.project_id == project_id,
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.entry_date >= period_start,
            TimesheetEntry.entry_date <= period_end,
        )
        .distinct()
        .order_by(TaskType.name)
    ).all()
    milestone_names = db.scalars(
        select(Milestone.name)
        .where(
            Milestone.project_id == project_id,
            Milestone.assigned_user_id == employee_id,
        )
        .order_by(Milestone.sort_order, Milestone.name)
    ).all()
    labels: list[str] = []
    for name in task_names:
        if name and name not in labels:
            labels.append(str(name))
    for name in milestone_names:
        if name and name not in labels:
            labels.append(str(name))
    if not labels:
        return None
    return ", ".join(labels[:12])


def discover_employee_projects(
    db: Session,
    employee_id: UUID,
    *,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    """Owned projects completed/worked in the review year; contributed = tool# + Supported."""
    owned: dict[UUID, dict[str, Any]] = {}
    supported: dict[UUID, dict[str, Any]] = {}

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
        owned[project.id] = _owned_project_row(project, employee_id)

    timesheet_rows = db.execute(
        select(
            TimesheetEntry.project_id,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
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

    for project_id, hours in timesheet_rows:
        if project_id is None:
            continue
        hours_decimal = Decimal(str(hours or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if project_id in owned:
            owned[project_id]["hours_logged"] = hours_decimal
            continue
        project = db.scalar(
            select(Project).options(selectinload(Project.customer)).where(Project.id == project_id)
        )
        if project is None or project.is_deleted:
            continue
        if _is_project_owner(project, employee_id):
            owned[project.id] = _owned_project_row(project, employee_id, hours_decimal)
        else:
            supported[project_id] = {
                "project_id": project.id,
                "tool_number": project.tool_number,
                "part_description": None,
                "customer_name": None,
                "assignment_role": "Supported",
                "hours_logged": hours_decimal,
                "execution_status": None,
                "project_stage": None,
                "completed_at": None,
                "ownership_type": "supported",
                "tasks_summary": None,
                "complexity": _project_complexity(project),
                "contribution_summary": "Supported",
                "achievement_notes": None,
            }

    # Only include owned projects completed in the review year (last July → this June)
    # or with timesheet hours logged in that same window.
    results: list[dict[str, Any]] = []
    owned_rows = sorted(
        owned.values(),
        key=lambda item: (
            -(float(item.get("hours_logged") or 0)),
            item.get("tool_number") or "",
        ),
    )
    for index, row in enumerate(owned_rows):
        hours = row.get("hours_logged") or Decimal("0")
        completed_at = row.get("completed_at")
        completed_in_period = bool(
            completed_at is not None and period_start <= completed_at <= period_end
        )
        worked_in_period = bool(hours > 0)
        if not (completed_in_period or worked_in_period):
            continue
        row["tasks_summary"] = _tasks_for_employee_project(
            db,
            employee_id,
            row["project_id"],
            period_start=period_start,
            period_end=period_end,
        )
        results.append(
            {
                **row,
                "contribution_summary": row.get("assignment_role"),
                "achievement_notes": None,
                "is_auto_imported": True,
                "sort_order": index,
            }
        )

    supported_start = len(results)
    for index, row in enumerate(
        sorted(supported.values(), key=lambda item: item.get("tool_number") or "")
    ):
        results.append(
            {
                **row,
                "is_auto_imported": True,
                "sort_order": supported_start + index,
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
                ownership_type=str(row.get("ownership_type") or "owned"),
                tasks_summary=row.get("tasks_summary"),
                complexity=row.get("complexity"),
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


def user_can_manage_team_reviews(db: Session, user: User, team_id: UUID | None) -> bool:
    if team_id is None:
        return is_admin(db, user)
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
    if _user_has_performance_action(db, user, MODULE_ACTION_EDIT) or _user_has_performance_action(
        db, user, MODULE_ACTION_EDIT_REVIEWS
    ) or _user_has_performance_action(db, user, MODULE_ACTION_CREATE):
        accessible = get_accessible_team_ids(db, user)
        if accessible is None:
            return True
        return team_id in accessible
    return False


def _user_has_performance_action(db: Session, user: User, action: str) -> bool:
    return user_has_module_action(
        user, get_role_name(db, user), MODULE_PERFORMANCE, action
    )


def review_is_locked(sheet: PerformanceReviewSheet) -> bool:
    if bool(getattr(sheet, "is_published", False)):
        return True
    stage = sheet.stage or STAGE_SELF
    return stage == STAGE_ACKNOWLEDGED or sheet.status == "acknowledged"


def user_can_edit_review_as_employee(db: Session, user: User, sheet: PerformanceReviewSheet) -> bool:
    if review_is_locked(sheet):
        return False
    if sheet.employee_id != user.id:
        return False
    return (sheet.stage or STAGE_SELF) == STAGE_SELF


def user_can_edit_review_as_manager(db: Session, user: User, sheet: PerformanceReviewSheet) -> bool:
    if review_is_locked(sheet):
        return False
    stage = sheet.stage or STAGE_SELF
    team_id = sheet.team_id
    has_scope = False
    if is_admin(db, user):
        has_scope = True
    elif team_id is not None and user_can_manage_team_reviews(db, user, team_id):
        has_scope = True
    elif sheet.reviewer_id == user.id:
        has_scope = True
    if not has_scope:
        return False
    if stage in (STAGE_MANAGER, STAGE_CALIBRATION, STAGE_FINAL, STAGE_SELF):
        return True
    return False


def user_can_edit_performance_review(db: Session, user: User, sheet: PerformanceReviewSheet) -> bool:
    return user_can_edit_review_as_employee(db, user, sheet) or user_can_edit_review_as_manager(
        db, user, sheet
    )


def user_can_create_performance_review(db: Session, user: User, team_id: UUID) -> bool:
    scoped = user_can_manage_team_reviews(db, user, team_id)
    if _user_has_performance_action(db, user, MODULE_ACTION_CREATE):
        return scoped
    if _user_has_performance_action(db, user, MODULE_ACTION_EDIT):
        return scoped
    if _user_has_performance_action(db, user, MODULE_ACTION_EDIT_REVIEWS):
        return scoped
    return scoped


def user_can_view_review(db: Session, user: User, sheet: PerformanceReviewSheet) -> bool:
    if sheet.employee_id == user.id or sheet.reviewer_id == user.id:
        return True
    if sheet.team_id is not None and user_can_manage_team_reviews(db, user, sheet.team_id):
        return True
    return False
