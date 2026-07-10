"""Project contributor aggregation for timesheets and reports."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Project, Timesheet, TimesheetEntry, User
from app.schemas.timesheet import ProjectContributorSummary


def _round_hours(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _user_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def get_project_contributors(db: Session, project_id: UUID) -> list[ProjectContributorSummary]:
    project = db.get(Project, project_id)
    if project is None:
        return []

    owner_ids = {uid for uid in (project.designer_id, project.surfacer_id) if uid is not None}

    rows = db.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .where(
            TimesheetEntry.project_id == project_id,
            TimesheetEntry.is_deleted.is_(False),
        )
        .group_by(User.id, User.first_name, User.last_name)
        .order_by(func.coalesce(func.sum(TimesheetEntry.hours), 0).desc())
    ).all()

    contributors: list[ProjectContributorSummary] = []
    for user_id, first_name, last_name, hours in rows:
        total = _round_hours(Decimal(str(hours or 0)))
        if total <= 0:
            continue
        is_owner = user_id in owner_ids
        role_label = "Contributor"
        if user_id == project.designer_id:
            role_label = "Assigned Designer"
        elif user_id == project.surfacer_id:
            role_label = "Assigned Surfacer"
        contributors.append(
            ProjectContributorSummary(
                user_id=user_id,
                user_name=f"{first_name} {last_name}".strip(),
                role_label=role_label,
                is_project_owner=is_owner,
                total_hours=total,
            )
        )
    return contributors


def get_project_contributors_map(
    db: Session, project_ids: list[UUID]
) -> dict[UUID, list[ProjectContributorSummary]]:
    if not project_ids:
        return {}
    return {project_id: get_project_contributors(db, project_id) for project_id in project_ids}
