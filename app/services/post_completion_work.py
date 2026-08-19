"""Classify timesheet hours logged after project completion."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ExecutionStatus, PostCompletionWorkType
from app.models.models import Project, Stream, Team, TimesheetEntry

COMMENT_REQUIRED_TYPES = frozenset(
    {
        PostCompletionWorkType.rework,
        PostCompletionWorkType.customer_change,
        PostCompletionWorkType.internal_correction,
    }
)

POST_COMPLETION_LABELS: dict[PostCompletionWorkType, str] = {
    PostCompletionWorkType.additional_work: "Additional Work",
    PostCompletionWorkType.rework: "Rework",
    PostCompletionWorkType.customer_change: "Customer Change",
    PostCompletionWorkType.internal_correction: "Internal Correction",
}


def coerce_post_completion_type(value: object | None) -> PostCompletionWorkType | None:
    if value is None or value == "":
        return None
    if isinstance(value, PostCompletionWorkType):
        return value
    try:
        return PostCompletionWorkType(str(value))
    except ValueError as exc:
        raise ProTrackValidationError("Invalid post-completion work type") from exc


def post_completion_hours_allowed(db: Session, project: Project) -> bool:
    if project.team_id is not None:
        team = db.get(Team, project.team_id)
        if team is not None and not bool(
            getattr(team, "allow_post_completion_timesheet", True)
        ):
            return False
    if project.stream_id is not None:
        stream = db.get(Stream, project.stream_id)
        if stream is not None and not bool(
            getattr(stream, "allow_post_completion_timesheet", True)
        ):
            return False
    return True


def apply_post_completion_rules(
    data: dict,
    *,
    db: Session,
    project: Project,
    existing: TimesheetEntry | None = None,
) -> None:
    work_type = coerce_post_completion_type(data.get("post_completion_type"))
    data["post_completion_type"] = work_type

    if project.execution_status != ExecutionStatus.completed:
        if work_type is not None:
            raise ProTrackValidationError(
                "Post-completion work type applies only to completed projects"
            )
        data["post_completion_type"] = None
        return

    if not post_completion_hours_allowed(db, project):
        raise ProTrackValidationError(
            "This team or workstream does not allow timesheet hours after project completion"
        )

    grandfathered_original = (
        existing is not None
        and getattr(existing, "post_completion_type", None) is None
        and existing.project_id == project.id
    )
    if work_type is None and not grandfathered_original:
        raise ProTrackValidationError(
            "Project is completed. Select a post-completion work type "
            "(Additional Work, Rework, Customer Change, or Internal Correction)."
        )

    if work_type in COMMENT_REQUIRED_TYPES:
        comment = str(data.get("description") or "").strip()
        if len(comment) < 8:
            raise ProTrackValidationError(
                f"{POST_COMPLETION_LABELS[work_type]} requires a comment explaining the reason"
            )


def hours_by_post_completion_type(
    db: Session, project_ids: list[UUID]
) -> dict[UUID, dict[PostCompletionWorkType | None, Decimal]]:
    if not project_ids:
        return {}
    rows = db.execute(
        select(
            TimesheetEntry.project_id,
            TimesheetEntry.post_completion_type,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .where(
            TimesheetEntry.project_id.in_(project_ids),
            TimesheetEntry.is_deleted.is_(False),
        )
        .group_by(TimesheetEntry.project_id, TimesheetEntry.post_completion_type)
    ).all()
    result: dict[UUID, dict[PostCompletionWorkType | None, Decimal]] = {
        pid: {} for pid in project_ids
    }
    for project_id, work_type, hours in rows:
        result.setdefault(project_id, {})[work_type] = Decimal(str(hours or 0))
    return result


def completed_post_completion_metrics(
    db: Session,
    *,
    month_start: date,
    month_end: date,
    team_ids: set[UUID] | frozenset[UUID] | None = None,
) -> dict[str, Decimal | int]:
    """Counts for completed projects that still have classified post-completion hours."""
    stmt = (
        select(
            TimesheetEntry.project_id,
            Project.customer_id,
            TimesheetEntry.post_completion_type,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(Project, TimesheetEntry.project_id == Project.id)
        .where(
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.post_completion_type.is_not(None),
            Project.execution_status == ExecutionStatus.completed,
            Project.is_deleted.is_(False),
        )
        .group_by(
            TimesheetEntry.project_id,
            Project.customer_id,
            TimesheetEntry.post_completion_type,
        )
    )
    if team_ids is not None:
        stmt = stmt.where(Project.team_id.in_(tuple(team_ids)))
    rows = db.execute(stmt).all()

    additional_projects: set[UUID] = set()
    rework_projects: set[UUID] = set()
    rework_customers: set[UUID] = set()
    hours_by_project: dict[UUID, Decimal] = {}

    for project_id, customer_id, work_type, hours in rows:
        amount = Decimal(str(hours or 0))
        hours_by_project[project_id] = hours_by_project.get(project_id, Decimal("0")) + amount
        if work_type == PostCompletionWorkType.additional_work:
            additional_projects.add(project_id)
        elif work_type == PostCompletionWorkType.rework:
            rework_projects.add(project_id)
            if customer_id is not None:
                rework_customers.add(customer_id)

    month_stmt = (
        select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .join(Project, TimesheetEntry.project_id == Project.id)
        .where(
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.post_completion_type.is_not(None),
            TimesheetEntry.entry_date >= month_start,
            TimesheetEntry.entry_date <= month_end,
            Project.execution_status == ExecutionStatus.completed,
            Project.is_deleted.is_(False),
        )
    )
    if team_ids is not None:
        month_stmt = month_stmt.where(Project.team_id.in_(tuple(team_ids)))
    month_hours = Decimal(str(db.scalar(month_stmt) or 0))

    unusual = sum(1 for total in hours_by_project.values() if total >= Decimal("20"))
    return {
        "completed_with_additional_work": len(additional_projects),
        "completed_with_rework": len(rework_projects),
        "post_completion_hours_this_month": month_hours,
        "customers_with_rework": len(rework_customers),
        "projects_high_post_completion_hours": unusual,
    }
