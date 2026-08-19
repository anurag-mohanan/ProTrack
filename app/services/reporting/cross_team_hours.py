"""Cross-team timesheet hours — members booking on another team's projects."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TimesheetStatus, WorkCategory
from app.models.models import Customer, Project, Team, Timesheet, TimesheetEntry, User
from app.schemas.reporting import CrossTeamHoursRow
from app.services.reporting.team_membership_windows import (
    home_team_id_on,
    primary_home_team_timeline,
)
from app.services.reporting.timesheet_attribution import resolve_home_team_id


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def build_cross_team_hours(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    team_id: UUID | None = None,
    customer_id: UUID | None = None,
    user_ids: set[UUID] | frozenset[UUID] | None = None,
) -> tuple[list[CrossTeamHoursRow], Decimal, Decimal]:
    """Return (rows, outbound_hours, inbound_hours).

    Cross-team = contributor's **primary home team as of the entry date** differs
    from ``Project.team_id`` (transfers must not rewrite historical home team).
    When ``team_id`` is set:
      - outbound: home team is scoped team, project team is different
      - inbound: project team is scoped team, home team is different
    When unset, every cross-team booking is listed (direction = cross).
    """
    stmt = (
        select(
            Timesheet.user_id,
            User.first_name,
            User.last_name,
            User.team_id,
            TimesheetEntry.entry_date,
            TimesheetEntry.project_id,
            TimesheetEntry.hours,
            TimesheetEntry.contribution_reason,
            TimesheetEntry.home_team_id,
            Project.tool_number,
            Project.team_id,
            Customer.name,
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .join(Project, TimesheetEntry.project_id == Project.id)
        .outerjoin(Customer, Project.customer_id == Customer.id)
        .where(
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.project_id.is_not(None),
            TimesheetEntry.work_category == WorkCategory.productive,
            TimesheetEntry.entry_date >= start_date,
            TimesheetEntry.entry_date <= end_date,
            Timesheet.status.in_(
                (
                    TimesheetStatus.draft,
                    TimesheetStatus.submitted,
                    TimesheetStatus.approved,
                )
            ),
            User.is_deleted.is_(False),
            Project.is_deleted.is_(False),
            Project.team_id.is_not(None),
        )
    )
    if customer_id is not None:
        stmt = stmt.where(Project.customer_id == customer_id)
    if user_ids is not None:
        if not user_ids:
            return [], Decimal("0"), Decimal("0")
        stmt = stmt.where(User.id.in_(tuple(user_ids)))

    raw_rows = list(db.execute(stmt).all())
    if not raw_rows:
        return [], Decimal("0"), Decimal("0")

    contributor_ids = {row[0] for row in raw_rows}
    timelines = primary_home_team_timeline(
        db,
        contributor_ids,
        range_start=start_date,
        range_end=end_date,
    )
    team_names = {
        row.id: row.name
        for row in db.scalars(select(Team).where(Team.is_active.is_(True))).all()
    }

    # Aggregate by (user, project, direction)
    buckets: dict[tuple[UUID, UUID, str], dict] = {}
    outbound_total = Decimal("0")
    inbound_total = Decimal("0")

    for (
        user_id,
        first_name,
        last_name,
        current_team_id,
        entry_date,
        project_id,
        hours,
        reason,
        snapshot_home_id,
        tool_number,
        project_team_id,
        customer_name,
    ) in raw_rows:
        if project_id is None or project_team_id is None or entry_date is None:
            continue
        hour_value = _decimal(hours)
        if hour_value <= 0:
            continue

        home_team_id = resolve_home_team_id(
            snapshot_home_team_id=snapshot_home_id,
            entry_date=entry_date,
            user=None,
            timeline=timelines.get(user_id),
        )
        if home_team_id is None and not timelines.get(user_id):
            home_team_id = current_team_id
        if home_team_id is None or home_team_id == project_team_id:
            continue

        if team_id is not None:
            if home_team_id == team_id and project_team_id != team_id:
                direction = "outbound"
            elif project_team_id == team_id and home_team_id != team_id:
                direction = "inbound"
            else:
                continue
        else:
            direction = "cross"

        key = (user_id, project_id, direction)
        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = {
                "user_id": user_id,
                "designer_name": f"{first_name} {last_name}".strip(),
                "home_team_id": home_team_id,
                "home_team_name": team_names.get(home_team_id),
                "project_id": project_id,
                "tool_number": tool_number,
                "project_team_id": project_team_id,
                "project_team_name": team_names.get(project_team_id),
                "customer_name": customer_name,
                "hours": hour_value,
                "contribution_reason": (
                    reason.value if reason is not None else None
                ),
                "direction": direction,
            }
        else:
            bucket["hours"] += hour_value

        if direction == "outbound":
            outbound_total += hour_value
        elif direction == "inbound":
            inbound_total += hour_value
        else:
            # Unscoped: count once toward outbound KPI for totals display
            outbound_total += hour_value

    rows = [
        CrossTeamHoursRow(
            direction=data["direction"],
            user_id=data["user_id"],
            designer_name=data["designer_name"],
            home_team_id=data["home_team_id"],
            home_team_name=data["home_team_name"],
            project_id=data["project_id"],
            tool_number=data["tool_number"],
            project_team_id=data["project_team_id"],
            project_team_name=data["project_team_name"],
            customer_name=data["customer_name"],
            hours=data["hours"],
            contribution_reason=data["contribution_reason"],
        )
        for data in buckets.values()
    ]
    rows.sort(
        key=lambda r: (
            0 if r.direction == "outbound" else 1 if r.direction == "inbound" else 2,
            -(r.hours or 0),
            r.designer_name.lower(),
            r.tool_number.lower(),
        )
    )
    return rows, outbound_total, inbound_total
