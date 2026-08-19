"""Attribute timesheet hours by home team as-of entry date, not live User.team_id."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import WorkCategory
from app.models.models import Project, Timesheet, TimesheetEntry, User
from app.services.reporting.team_membership_windows import (
    home_team_id_on,
    primary_home_team_timeline,
)

HomeTimeline = dict[UUID, list[tuple[date, date, UUID]]]


def snapshot_home_team_id(db: Session, user_id: UUID, as_of: date) -> UUID | None:
    """Primary home on ``as_of`` for stamping a new/edited entry."""
    timelines = primary_home_team_timeline(
        db, {user_id}, range_start=as_of, range_end=as_of
    )
    found = home_team_id_on(timelines.get(user_id), as_of)
    if found is not None:
        return found
    user = db.get(User, user_id)
    return user.team_id if user is not None else None


def stamp_home_team_on_entry(db: Session, entry: TimesheetEntry) -> None:
    timesheet = db.get(Timesheet, entry.timesheet_id)
    if timesheet is None or entry.entry_date is None:
        return
    entry.home_team_id = snapshot_home_team_id(db, timesheet.user_id, entry.entry_date)


def resolve_home_team_id(
    *,
    snapshot_home_team_id: UUID | None,
    entry_date: date,
    user: User | None,
    timeline: list[tuple[date, date, UUID]] | None,
) -> UUID | None:
    """Prefer snapshot; else period timeline; never current team if a stint history exists."""
    if snapshot_home_team_id is not None:
        return snapshot_home_team_id
    found = home_team_id_on(timeline, entry_date)
    if found is not None:
        return found
    if timeline:
        return None
    return user.team_id if user is not None else None


def resolve_entry_home_team_id(
    *,
    entry: TimesheetEntry,
    user: User | None,
    timeline: list[tuple[date, date, UUID]] | None,
) -> UUID | None:
    return resolve_home_team_id(
        snapshot_home_team_id=getattr(entry, "home_team_id", None),
        entry_date=entry.entry_date,
        user=user,
        timeline=timeline,
    )


def work_context_team_id(
    entry: TimesheetEntry,
    project: Project | None,
    *,
    resolved_home_team_id: UUID | None = None,
) -> UUID | None:
    """Delivery team for customer/project hours (not the employee's current home)."""
    if (
        entry.work_category == WorkCategory.productive
        and project is not None
        and project.team_id is not None
    ):
        return project.team_id
    if resolved_home_team_id is not None:
        return resolved_home_team_id
    return getattr(entry, "home_team_id", None)
