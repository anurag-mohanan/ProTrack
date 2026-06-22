from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.project_metrics import build_project_read, calculate_progress_percent
from app.models.enums import MilestoneStatus, ProjectStatus
from app.models.models import Milestone, Project, Role, Timesheet, TimesheetEntry, User
from app.schemas.dashboard import (
    DashboardSummary,
    DesignerWorkload,
    MilestoneSummary,
    ProjectDashboard,
    ProjectHoursSummary,
)
from app.schemas.timesheet import TimesheetEntryRead

WORKLOAD_ROLES = ("Designer", "Design Leader", "Surfacer")


def _round_percent(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_hours(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _current_week_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _project_assignment_filter(user_id: UUID, role_name: str):
    if role_name == "Design Leader":
        return Project.design_leader_id == user_id
    if role_name == "Designer":
        return Project.designer_id == user_id
    if role_name == "Surfacer":
        return Project.surfacer_id == user_id
    return None


def get_dashboard_summary(db: Session) -> DashboardSummary:
    projects = db.scalars(select(Project)).all()
    total_projects = len(projects)
    not_started = sum(1 for p in projects if p.status == ProjectStatus.not_started)
    in_progress = sum(1 for p in projects if p.status == ProjectStatus.in_progress)
    completed = sum(1 for p in projects if p.status == ProjectStatus.completed)
    on_hold = sum(1 for p in projects if p.status == ProjectStatus.waiting_for_customer)

    total_quoted = _round_hours(
        sum((Decimal(p.quoted_hours) for p in projects), Decimal("0"))
    )
    total_actual = _round_hours(
        sum((Decimal(p.actual_hours or 0) for p in projects), Decimal("0"))
    )

    completed_milestones = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(Milestone.status == MilestoneStatus.completed)
        )
        or 0
    )
    total_milestones = int(
        db.scalar(select(func.count()).select_from(Milestone)) or 0
    )

    if total_milestones == 0:
        overall_progress = Decimal("0.00")
    else:
        overall_progress = _round_percent(
            (Decimal(completed_milestones) / Decimal(total_milestones))
            * Decimal("100")
        )

    return DashboardSummary(
        total_projects=total_projects,
        not_started_projects=not_started,
        in_progress_projects=in_progress,
        completed_projects=completed,
        on_hold_projects=on_hold,
        total_quoted_hours=total_quoted,
        total_actual_hours=total_actual,
        hours_variance=_round_hours(total_actual - total_quoted),
        completed_milestones=completed_milestones,
        total_milestones=total_milestones,
        overall_progress_percent=overall_progress,
    )


def get_designer_workload(db: Session) -> list[DesignerWorkload]:
    week_start, week_end = _current_week_bounds()
    users = db.scalars(
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(Role.name.in_(WORKLOAD_ROLES), User.is_active.is_(True))
        .order_by(User.last_name, User.first_name)
    ).all()

    workload: list[DesignerWorkload] = []
    for user in users:
        role_name = user.role.name
        assignment_filter = _project_assignment_filter(user.id, role_name)
        if assignment_filter is None:
            continue

        assigned_projects = db.scalars(
            select(Project).where(assignment_filter)
        ).all()
        active_projects = sum(
            1 for project in assigned_projects if project.status != ProjectStatus.completed
        )
        quoted_hours_assigned = _round_hours(
            sum((Decimal(p.quoted_hours) for p in assigned_projects), Decimal("0"))
        )
        actual_hours_logged = _round_hours(
            sum((Decimal(p.actual_hours or 0) for p in assigned_projects), Decimal("0"))
        )

        hours_this_week = db.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
            .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(
                Timesheet.user_id == user.id,
                TimesheetEntry.entry_date >= week_start,
                TimesheetEntry.entry_date <= week_end,
            )
        )

        workload.append(
            DesignerWorkload(
                user_id=user.id,
                designer_name=f"{user.first_name} {user.last_name}",
                role=role_name,
                active_projects=active_projects,
                hours_this_week=_round_hours(Decimal(str(hours_this_week or 0))),
                quoted_hours_assigned=quoted_hours_assigned,
                actual_hours_logged=actual_hours_logged,
            )
        )

    return workload


def get_project_dashboard(db: Session, project_id: UUID) -> ProjectDashboard | None:
    project = db.get(Project, project_id)
    if project is None:
        return None

    completed = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(
                Milestone.project_id == project_id,
                Milestone.status == MilestoneStatus.completed,
            )
        )
        or 0
    )
    total = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(Milestone.project_id == project_id)
        )
        or 0
    )
    remaining = max(total - completed, 0)
    progress_percent = calculate_progress_percent(db, project_id)

    quoted = _round_hours(Decimal(project.quoted_hours))
    actual = _round_hours(Decimal(project.actual_hours or 0))

    recent_entries = db.scalars(
        select(TimesheetEntry)
        .where(TimesheetEntry.project_id == project_id)
        .order_by(TimesheetEntry.entry_date.desc(), TimesheetEntry.created_at.desc())
        .limit(10)
    ).all()

    return ProjectDashboard(
        project=build_project_read(db, project),
        milestone_summary=MilestoneSummary(
            completed=completed,
            remaining=remaining,
            progress_percent=progress_percent,
        ),
        hours=ProjectHoursSummary(
            quoted=quoted,
            actual=actual,
            variance=_round_hours(actual - quoted),
        ),
        recent_timesheet_entries=[
            TimesheetEntryRead.model_validate(entry, from_attributes=True)
            for entry in recent_entries
        ],
    )
