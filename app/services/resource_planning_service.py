"""Build designer × calendar resource planning grids."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.crud.team_reports import get_team_resource_planning
from app.models.enums import ExecutionStatus, MilestoneStatus, UserAvailabilityStatus
from app.models.models import Customer, Milestone, Project, Role, Team, TeamMember, User
from app.schemas.resource_planning import (
    ResourceAllocationBlock,
    ResourcePlanningCell,
    ResourcePlanningDesignerRow,
    ResourcePlanningGranularity,
    ResourcePlanningGrid,
    ResourcePlanningPeriod,
    UnassignedProjectBlock,
)
from app.services.dashboard_service import WORKLOAD_ROLES, _batch_current_milestones
from app.services.holiday_service import is_holiday
from app.services.project_calculation_service import calculate_hours


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


WEEKDAY_CODES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _user_works_on(user: User, day: date) -> bool:
    working_days = (user.working_days or "Mon,Tue,Wed,Thu,Fri").split(",")
    code = WEEKDAY_CODES[day.weekday()]
    return any(part.strip() == code for part in working_days)


def _daily_capacity(db: Session, user: User, day: date) -> Decimal:
    if user.availability_status in (
        UserAvailabilityStatus.on_leave,
        UserAvailabilityStatus.unavailable,
    ):
        return Decimal("0")
    if not _user_works_on(user, day):
        return Decimal("0")
    if is_holiday(db, day):
        return Decimal("0")
    return _decimal(user.working_hours_per_day or 8)


def _remaining_business_days(db: Session, start: date, end: date) -> int:
    if end < start:
        return 0
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5 and not is_holiday(db, current):
            count += 1
        current += timedelta(days=1)
    return max(count, 1)


def _cell_color(allocated: Decimal, capacity: Decimal) -> str:
    if capacity <= 0 and allocated <= 0:
        return "grey"
    if capacity <= 0 and allocated > 0:
        return "red"
    ratio = allocated / capacity if capacity > 0 else Decimal("1")
    if ratio > Decimal("1"):
        return "red"
    if ratio >= Decimal("0.85"):
        return "orange"
    if ratio >= Decimal("0.5"):
        return "blue"
    return "green"


def _block_color(project: Project, today: date) -> str:
    if project.execution_status == ExecutionStatus.on_hold:
        return "grey"
    if project.due_date < today and project.execution_status not in (
        ExecutionStatus.completed,
        ExecutionStatus.cancelled,
    ):
        return "red"
    if project.execution_status == ExecutionStatus.currently_being_worked_on:
        return "blue"
    return "orange"


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _build_periods(
    start: date,
    granularity: ResourcePlanningGranularity,
) -> tuple[list[ResourcePlanningPeriod], date]:
    periods: list[ResourcePlanningPeriod] = []

    if granularity == ResourcePlanningGranularity.day:
        end = start + timedelta(days=13)
        current = start
        while current <= end:
            periods.append(
                ResourcePlanningPeriod(
                    key=current.isoformat(),
                    label=current.strftime("%d %b"),
                    start_date=current,
                    end_date=current,
                )
            )
            current += timedelta(days=1)
        return periods, end

    if granularity == ResourcePlanningGranularity.week:
        week_start = _week_start(start)
        end = week_start + timedelta(days=7 * 8 - 1)
        current = week_start
        for index in range(8):
            week_end = current + timedelta(days=6)
            periods.append(
                ResourcePlanningPeriod(
                    key=current.isoformat(),
                    label=f"W{current.isocalendar().week} · {current.strftime('%d %b')}",
                    start_date=current,
                    end_date=week_end,
                )
            )
            current += timedelta(days=7)
        return periods, end

    month_cursor = date(start.year, start.month, 1)
    for _ in range(6):
        last_day = monthrange(month_cursor.year, month_cursor.month)[1]
        month_end = date(month_cursor.year, month_cursor.month, last_day)
        periods.append(
            ResourcePlanningPeriod(
                key=f"{month_cursor.year}-{month_cursor.month:02d}",
                label=month_cursor.strftime("%b %Y"),
                start_date=month_cursor,
                end_date=month_end,
            )
        )
        if month_cursor.month == 12:
            month_cursor = date(month_cursor.year + 1, 1, 1)
        else:
            month_cursor = date(month_cursor.year, month_cursor.month + 1, 1)
    return periods, periods[-1].end_date


def _designer_user_ids_for_team(db: Session, team_id: UUID | None) -> set[UUID] | None:
    if team_id is None:
        return None
    member_ids = set(
        db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team_id)).all()
    )
    assigned_ids = set(
        db.scalars(select(User.id).where(User.team_id == team_id, User.is_deleted.is_(False)).all())
    )
    return member_ids | assigned_ids


def _hours_for_project_on_day(
    db: Session,
    project: Project,
    day: date,
    today: date,
) -> Decimal:
    if project.execution_status in (
        ExecutionStatus.completed,
        ExecutionStatus.cancelled,
    ):
        return Decimal("0")
    if day > project.due_date:
        return Decimal("0")
    hours = calculate_hours(db, project)
    remaining = max(hours.remaining, Decimal("0"))
    spread_end = max(project.due_date, today)
    business_days = _remaining_business_days(db, today, spread_end)
    return _round(remaining / Decimal(business_days))


def get_resource_planning_grid(
    db: Session,
    *,
    start: date | None = None,
    granularity: ResourcePlanningGranularity = ResourcePlanningGranularity.week,
    team_id: UUID | None = None,
) -> ResourcePlanningGrid:
    today = date.today()
    anchor = start or today
    periods, end_date = _build_periods(anchor, granularity)
    team_user_ids = _designer_user_ids_for_team(db, team_id)

    designers = db.scalars(
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(
            Role.name.in_(WORKLOAD_ROLES),
            User.is_active.is_(True),
            User.is_archived.is_(False),
            User.is_deleted.is_(False),
        )
        .order_by(User.last_name, User.first_name)
    ).all()
    if team_user_ids is not None:
        designers = [designer for designer in designers if designer.id in team_user_ids]

    active_projects = db.scalars(
        select(Project)
        .where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.in_(
                (
                    ExecutionStatus.currently_being_worked_on,
                    ExecutionStatus.on_hold,
                )
            ),
        )
    ).all()
    if team_id is not None:
        active_projects = [
            project for project in active_projects if project.team_id == team_id
        ]

    customer_names = {
        row.id: row.name
        for row in db.scalars(
            select(Customer).where(
                Customer.id.in_({project.customer_id for project in active_projects})
            )
        ).all()
    }
    milestone_names = _batch_current_milestones(
        db, [project.id for project in active_projects]
    )

    team_names = {
        row.id: row.name
        for row in db.scalars(select(Team).where(Team.is_active.is_(True))).all()
    }

    designer_rows: list[ResourcePlanningDesignerRow] = []
    for designer in designers:
        assigned_projects = [
            project
            for project in active_projects
            if project.designer_id == designer.id
            or project.design_leader_id == designer.id
        ]
        cells: list[ResourcePlanningCell] = []
        total_capacity = Decimal("0")
        total_allocated = Decimal("0")

        for period in periods:
            period_capacity = Decimal("0")
            period_allocated = Decimal("0")
            blocks: list[ResourceAllocationBlock] = []

            day = period.start_date
            while day <= period.end_date:
                day_capacity = _daily_capacity(db, designer, day)
                period_capacity += day_capacity

                for project in assigned_projects:
                    day_hours = _hours_for_project_on_day(db, project, day, today)
                    if day_hours <= 0:
                        continue
                    period_allocated += day_hours
                    existing = next(
                        (block for block in blocks if block.project_id == project.id),
                        None,
                    )
                    if existing:
                        blocks = [
                            ResourceAllocationBlock(
                                project_id=block.project_id,
                                tool_number=block.tool_number,
                                customer_name=block.customer_name,
                                milestone_name=block.milestone_name,
                                hours=_round(block.hours + day_hours),
                                status_color=block.status_color,
                            )
                            if block.project_id == project.id
                            else block
                            for block in blocks
                        ]
                    else:
                        blocks.append(
                            ResourceAllocationBlock(
                                project_id=project.id,
                                tool_number=project.tool_number,
                                customer_name=customer_names.get(
                                    project.customer_id, "—"
                                ),
                                milestone_name=milestone_names.get(project.id),
                                hours=day_hours,
                                status_color=_block_color(project, today),
                            )
                        )
                day += timedelta(days=1)

            period_capacity = _round(period_capacity)
            period_allocated = _round(period_allocated)
            remaining = _round(max(period_capacity - period_allocated, Decimal("0")))
            total_capacity += period_capacity
            total_allocated += period_allocated

            cells.append(
                ResourcePlanningCell(
                    period_key=period.key,
                    capacity_hours=period_capacity,
                    allocated_hours=period_allocated,
                    remaining_hours=remaining,
                    status_color=_cell_color(period_allocated, period_capacity),
                    blocks=blocks,
                )
            )

        designer_rows.append(
            ResourcePlanningDesignerRow(
                user_id=designer.id,
                designer_name=f"{designer.first_name} {designer.last_name}",
                team_name=team_names.get(designer.team_id) if designer.team_id else None,
                availability_status=(
                    designer.availability_status.value
                    if designer.availability_status
                    else "available"
                ),
                capacity_hours=_round(total_capacity),
                allocated_hours=_round(total_allocated),
                remaining_hours=_round(max(total_capacity - total_allocated, Decimal("0"))),
                cells=cells,
            )
        )

    unassigned: list[UnassignedProjectBlock] = []
    for project in active_projects:
        if project.designer_id is not None:
            continue
        hours = calculate_hours(db, project)
        unassigned.append(
            UnassignedProjectBlock(
                project_id=project.id,
                tool_number=project.tool_number,
                customer_name=customer_names.get(project.customer_id, "—"),
                quoted_hours=hours.quoted,
                remaining_hours=hours.remaining,
                due_date=project.due_date,
                milestone_name=milestone_names.get(project.id),
            )
        )

    return ResourcePlanningGrid(
        granularity=granularity,
        start_date=periods[0].start_date if periods else anchor,
        end_date=end_date,
        periods=periods,
        designers=designer_rows,
        unassigned_projects=unassigned,
        team_summary=get_team_resource_planning(db, team_id=team_id),
    )
