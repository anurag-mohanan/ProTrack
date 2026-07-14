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
from app.models.models import Customer, Milestone, Project, Team, TeamMember, User
from app.schemas.resource_planning import (
    ResourceAllocationBlock,
    ResourcePlanningCell,
    ResourcePlanningDesignerRow,
    ResourcePlanningGranularity,
    ResourcePlanningGrid,
    ResourcePlanningPeriod,
    UnassignedProjectBlock,
)
from app.services.dashboard_service import _batch_current_milestones
from app.services.kpi_participation import capacity_planning_users
from app.services.holiday_service import is_holiday_cached, load_holiday_dates
from app.services.project_calculation_service import batch_calculate_hours


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


# Floor load when a live tool has incomplete milestones but no planned hours set.
_OPEN_MILESTONE_FLOOR_HOURS = Decimal("16")
# Carry one week of work when project is still CBW/planning with no open MS hours.
_ACTIVE_TOOL_CARRY_HOURS = Decimal("40")


def _batch_open_milestone_load(
    db: Session,
    project_ids: list[UUID],
) -> dict[UUID, tuple[Decimal, int, int]]:
    """project_id → (open planned hours, open milestone count, total milestone count)."""
    if not project_ids:
        return {}
    milestones = db.scalars(
        select(Milestone).where(Milestone.project_id.in_(project_ids))
    ).all()
    result: dict[UUID, tuple[Decimal, int, int]] = {
        project_id: (Decimal("0"), 0, 0) for project_id in project_ids
    }
    for milestone in milestones:
        planned, open_count, total = result[milestone.project_id]
        total += 1
        if milestone.status != MilestoneStatus.completed:
            open_count += 1
            planned += _decimal(milestone.planned_hours)
        result[milestone.project_id] = (planned, open_count, total)
    return result


def _active_planning_remaining(
    project: Project,
    *,
    actual_hours: Decimal,
    open_planned: Decimal,
    open_count: int,
    milestone_total: int,
) -> Decimal:
    """Remaining hours to schedule for a live tool (Ops/EM rule).

    Never drop to zero solely because actual already exceeds quoted/planned —
    designers on active tools still consume capacity until the tool is closed.
    """
    planned_total = _decimal(project.current_planned_hours)
    quoted = _decimal(project.quoted_hours)
    budget = planned_total if planned_total > 0 else quoted

    if open_planned > 0:
        return _round(open_planned)

    if budget > 0:
        leftover = max(budget - actual_hours, Decimal("0"))
        if leftover > 0:
            return _round(leftover)

    # Over-burn or missing milestone plans — still schedule open scope.
    if open_count > 0:
        if quoted > 0 and milestone_total > 0:
            return _round((quoted / Decimal(milestone_total)) * Decimal(open_count))
        return _round(Decimal(open_count) * _OPEN_MILESTONE_FLOOR_HOURS)

    if project.execution_status in (
        ExecutionStatus.currently_being_worked_on,
        ExecutionStatus.planning,
    ):
        return _ACTIVE_TOOL_CARRY_HOURS

    return Decimal("0")


WEEKDAY_CODES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _user_works_on(user: User, day: date) -> bool:
    working_days = (user.working_days or "Mon,Tue,Wed,Thu,Fri").split(",")
    code = WEEKDAY_CODES[day.weekday()]
    return any(part.strip() == code for part in working_days)


def _daily_capacity(
    user: User,
    day: date,
    holidays: set[date],
) -> Decimal:
    if user.availability_status in (
        UserAvailabilityStatus.on_leave,
        UserAvailabilityStatus.unavailable,
    ):
        return Decimal("0")
    if not _user_works_on(user, day):
        return Decimal("0")
    if is_holiday_cached(holidays, day):
        return Decimal("0")
    return _decimal(user.working_hours_per_day or 8)


def _remaining_business_days(
    start: date,
    end: date,
    holidays: set[date],
) -> int:
    if end < start:
        return 0
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5 and not is_holiday_cached(holidays, current):
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
    if (
        project.due_date is not None
        and project.due_date < today
        and project.execution_status
        not in (
            ExecutionStatus.completed,
            ExecutionStatus.cancelled,
        )
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


def _designer_user_ids_for_team(
    db: Session,
    team_id: UUID | None = None,
    team_ids: list[UUID] | None = None,
) -> set[UUID] | None:
    scoped_ids = [team_id] if team_id is not None else team_ids
    if scoped_ids is None:
        return None
    if not scoped_ids:
        return set()
    member_ids = set(
        db.scalars(select(TeamMember.user_id).where(TeamMember.team_id.in_(scoped_ids))).all()
    )
    assigned_ids = set(
        db.scalars(
            select(User.id).where(
                User.team_id.in_(scoped_ids),
                User.is_deleted.is_(False),
            )
        ).all()
    )
    return member_ids | assigned_ids


def _hours_for_project_on_day(
    project: Project,
    day: date,
    today: date,
    *,
    remaining_hours: Decimal,
    business_days: int,
    holidays: set[date],
    spread_end: date,
) -> Decimal:
    if project.execution_status in (
        ExecutionStatus.completed,
        ExecutionStatus.cancelled,
    ):
        return Decimal("0")
    if day < today or day > spread_end:
        return Decimal("0")
    if day.weekday() >= 5 or is_holiday_cached(holidays, day):
        return Decimal("0")
    if business_days <= 0:
        return Decimal("0")
    return _round(remaining_hours / Decimal(business_days))


def _assignment_share(user_id: UUID, project: Project) -> Decimal:
    """Fraction of remaining delivery hours attributed to this person.

    Ops/EM rule: primary designer owns remaining work. Design leaders who are
    not the designer get a light oversight share (not a full second copy).
    Surfacers get a craft share when also assigned.
    """
    is_designer = project.designer_id == user_id
    is_dl = project.design_leader_id == user_id
    is_surfacer = project.surfacer_id == user_id

    if is_designer and is_dl:
        return Decimal("1")
    if is_designer:
        return Decimal("1")
    if is_surfacer and not is_designer:
        return Decimal("0.40") if project.designer_id else Decimal("1")
    if is_dl and not is_designer:
        return Decimal("0.15")
    return Decimal("0")


def _derive_load_status(
    user: User,
    *,
    total_allocated: Decimal,
    total_capacity: Decimal,
    has_live_assignment: bool,
) -> str:
    if user.availability_status in (
        UserAvailabilityStatus.on_leave,
        UserAvailabilityStatus.unavailable,
    ):
        return "on_leave"
    if total_capacity <= 0:
        return "unavailable"
    util = total_allocated / total_capacity
    if has_live_assignment or util >= Decimal("0.01"):
        if util >= Decimal("1"):
            return "overloaded"
        return "allocated"
    return "available"


def get_resource_planning_grid(
    db: Session,
    *,
    start: date | None = None,
    granularity: ResourcePlanningGranularity = ResourcePlanningGranularity.week,
    team_id: UUID | None = None,
    team_ids: list[UUID] | None = None,
) -> ResourcePlanningGrid:
    today = date.today()
    anchor = start or today
    periods, end_date = _build_periods(anchor, granularity)
    team_user_ids = _designer_user_ids_for_team(db, team_id=team_id, team_ids=team_ids)
    holidays = load_holiday_dates(db, anchor, end_date)

    designers = capacity_planning_users(db)
    if team_user_ids is not None:
        designers = [designer for designer in designers if designer.id in team_user_ids]

    live_statuses = (
        ExecutionStatus.planning,
        ExecutionStatus.currently_being_worked_on,
        ExecutionStatus.on_hold,
    )
    active_projects = db.scalars(
        select(Project)
        .where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.in_(live_statuses),
        )
    ).all()
    scoped_team_ids = [team_id] if team_id is not None else team_ids
    if scoped_team_ids is not None:
        allowed = set(scoped_team_ids)
        active_projects = [
            project
            for project in active_projects
            if project.team_id is not None and project.team_id in allowed
        ]

    customer_ids = {project.customer_id for project in active_projects}
    customer_names = {
        row.id: row.name
        for row in db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
    } if customer_ids else {}
    milestone_names = _batch_current_milestones(
        db, [project.id for project in active_projects]
    )

    team_names = {
        row.id: row.name
        for row in db.scalars(select(Team).where(Team.is_active.is_(True))).all()
    }

    project_hours = batch_calculate_hours(db, active_projects)
    open_load = _batch_open_milestone_load(db, [project.id for project in active_projects])
    # remaining_hours, business_days, spread_end
    project_daily_rates: dict[UUID, tuple[Decimal, int, date]] = {}
    for project in active_projects:
        hours = project_hours.get(project.id)
        if hours is None:
            continue
        open_planned, open_count, milestone_total = open_load.get(
            project.id, (Decimal("0"), 0, 0)
        )
        remaining = _active_planning_remaining(
            project,
            actual_hours=hours.actual,
            open_planned=open_planned,
            open_count=open_count,
            milestone_total=milestone_total,
        )
        # Overdue or undated tools still show remaining pressure over a runway.
        if project.due_date and project.due_date >= today:
            spread_end = project.due_date
        else:
            spread_end = today + timedelta(days=14)
        spread_end = max(spread_end, today)
        business_days = _remaining_business_days(today, spread_end, holidays)
        project_daily_rates[project.id] = (remaining, business_days, spread_end)

    designer_rows: list[ResourcePlanningDesignerRow] = []
    for designer in designers:
        assigned_projects = [
            project
            for project in active_projects
            if project.designer_id == designer.id
            or project.design_leader_id == designer.id
            or project.surfacer_id == designer.id
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
                day_capacity = _daily_capacity(designer, day, holidays)
                period_capacity += day_capacity

                for project in assigned_projects:
                    rate = project_daily_rates.get(project.id)
                    if rate is None:
                        continue
                    remaining_hours, business_days, spread_end = rate
                    share = _assignment_share(designer.id, project)
                    if share <= 0:
                        continue
                    day_hours = _hours_for_project_on_day(
                        project,
                        day,
                        today,
                        remaining_hours=remaining_hours * share,
                        business_days=business_days,
                        holidays=holidays,
                        spread_end=spread_end,
                    )
                    if day_hours <= 0:
                        continue
                    period_allocated += day_hours
                    complexity = (
                        project.complexity.value
                        if getattr(project, "complexity", None)
                        else None
                    )
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
                                complexity=block.complexity,
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
                                complexity=complexity,
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

        has_live = bool(assigned_projects)
        designer_rows.append(
            ResourcePlanningDesignerRow(
                user_id=designer.id,
                designer_name=f"{designer.first_name} {designer.last_name}",
                team_name=team_names.get(designer.team_id) if designer.team_id else None,
                availability_status=_derive_load_status(
                    designer,
                    total_allocated=total_allocated,
                    total_capacity=total_capacity,
                    has_live_assignment=has_live,
                ),
                skill_level=(
                    designer.skill_level.value if designer.skill_level else None
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
        hours = project_hours.get(project.id)
        if hours is None:
            continue
        open_planned, open_count, milestone_total = open_load.get(
            project.id, (Decimal("0"), 0, 0)
        )
        remaining = _active_planning_remaining(
            project,
            actual_hours=hours.actual,
            open_planned=open_planned,
            open_count=open_count,
            milestone_total=milestone_total,
        )
        unassigned.append(
            UnassignedProjectBlock(
                project_id=project.id,
                tool_number=project.tool_number,
                customer_name=customer_names.get(project.customer_id, "—"),
                quoted_hours=_round(_decimal(project.quoted_hours)),
                remaining_hours=_round(remaining),
                due_date=project.due_date,
                milestone_name=milestone_names.get(project.id),
                complexity=(
                    project.complexity.value if getattr(project, "complexity", None) else None
                ),
            )
        )

    team_summary = get_team_resource_planning(db, team_id=team_id)

    return ResourcePlanningGrid(
        granularity=granularity,
        start_date=periods[0].start_date if periods else anchor,
        end_date=end_date,
        periods=periods,
        designers=designer_rows,
        unassigned_projects=unassigned,
        team_summary=team_summary,
    )
