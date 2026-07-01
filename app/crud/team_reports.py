"""Team-based reporting and resource planning."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import extract, func, select

from app.crud.base import Session
from app.crud.dashboard import _round_hours, get_designer_workload
from app.models.enums import ExecutionStatus, TimesheetStatus, WorkCategory
from app.models.models import (
    Customer,
    Project,
    Team,
    TeamMember,
    Timesheet,
    TimesheetEntry,
    User,
)
from app.schemas.reports import (
    CustomerByTeamReportRow,
    DesignerByTeamReportRow,
    HoursByTeamReportRow,
    MonthlyTeamSummaryRow,
    ProjectsByTeamReportRow,
    QuotedVsActualByTeamReportRow,
    TeamProfitabilityReportRow,
    TeamResourcePlanningRow,
    TeamUtilizationReportRow,
)
from app.services.project_calculation_service import calculate_hours


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _project_base_stmt(*, include_archived: bool = True, include_deleted: bool = False):
    stmt = select(Project)
    if not include_deleted:
        stmt = stmt.where(Project.is_deleted.is_(False))
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    return stmt


def get_projects_by_team_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
    team_id: UUID | None = None,
) -> list[ProjectsByTeamReportRow]:
    stmt = (
        select(
            Team.id,
            Team.name,
            Team.colour,
            func.count(Project.id),
        )
        .outerjoin(Project, Project.team_id == Team.id)
        .where(Team.is_active.is_(True))
        .group_by(Team.id, Team.name, Team.colour)
        .order_by(Team.name)
    )
    if not include_deleted:
        stmt = stmt.where((Project.id.is_(None)) | (Project.is_deleted.is_(False)))
    if not include_archived:
        stmt = stmt.where((Project.id.is_(None)) | (Project.is_archived.is_(False)))
    if team_id is not None:
        stmt = stmt.where(Team.id == team_id)

    rows = db.execute(stmt).all()
    return [
        ProjectsByTeamReportRow(
            team_id=row[0],
            team_name=row[1],
            team_colour=row[2],
            project_count=int(row[3] or 0),
        )
        for row in rows
    ]


def get_hours_by_team_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
    team_id: UUID | None = None,
) -> list[HoursByTeamReportRow]:
    stmt = (
        select(
            Team.id,
            Team.name,
            func.coalesce(func.sum(Project.quoted_hours), 0),
            func.coalesce(func.sum(Project.actual_hours), 0),
        )
        .outerjoin(Project, Project.team_id == Team.id)
        .where(Team.is_active.is_(True))
        .group_by(Team.id, Team.name)
        .order_by(Team.name)
    )
    if not include_deleted:
        stmt = stmt.where((Project.id.is_(None)) | (Project.is_deleted.is_(False)))
    if not include_archived:
        stmt = stmt.where((Project.id.is_(None)) | (Project.is_archived.is_(False)))
    if team_id is not None:
        stmt = stmt.where(Team.id == team_id)

    report: list[HoursByTeamReportRow] = []
    for row in db.execute(stmt).all():
        quoted = _round_hours(_decimal(row[2]))
        actual = _round_hours(_decimal(row[3]))
        report.append(
            HoursByTeamReportRow(
                team_id=row[0],
                team_name=row[1],
                quoted_hours=quoted,
                actual_hours=actual,
                hours_variance=_round_hours(actual - quoted),
            )
        )
    return report


def get_quoted_vs_actual_by_team_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
    team_id: UUID | None = None,
) -> list[QuotedVsActualByTeamReportRow]:
    return [
        QuotedVsActualByTeamReportRow(
            team_id=row.team_id,
            team_name=row.team_name,
            quoted_hours=row.quoted_hours,
            actual_hours=row.actual_hours,
            variance_hours=row.hours_variance,
            variance_percent=(
                _round_hours((row.hours_variance / row.quoted_hours) * Decimal("100"))
                if row.quoted_hours > 0
                else Decimal("0.00")
            ),
        )
        for row in get_hours_by_team_report(
            db,
            include_archived=include_archived,
            include_deleted=include_deleted,
            team_id=team_id,
        )
    ]


def get_team_utilization_report(
    db: Session,
    *,
    team_id: UUID | None = None,
) -> list[TeamUtilizationReportRow]:
    workload = get_designer_workload(db)
    members = db.scalars(select(TeamMember)).all()
    user_teams: dict[UUID, list[str]] = {}
    for member in members:
        team = db.get(Team, member.team_id)
        if team is None or not team.is_active:
            continue
        if team_id is not None and team.id != team_id:
            continue
        user_teams.setdefault(member.user_id, []).append(team.name)

    by_team: dict[str, TeamUtilizationReportRow] = {}
    for row in workload:
        team_names = user_teams.get(row.user_id, ["Unassigned"])
        for team_name in team_names:
            bucket = by_team.get(team_name)
            if bucket is None:
                team = db.scalar(select(Team).where(Team.name == team_name))
                by_team[team_name] = TeamUtilizationReportRow(
                    team_id=team.id if team else None,
                    team_name=team_name,
                    member_count=0,
                    allocated_hours=Decimal("0"),
                    actual_hours=Decimal("0"),
                    utilization_percent=Decimal("0"),
                )
                bucket = by_team[team_name]
            bucket.member_count += 1
            bucket.allocated_hours = _round_hours(
                bucket.allocated_hours + _decimal(row.quoted_hours_assigned)
            )
            bucket.actual_hours = _round_hours(
                bucket.actual_hours + _decimal(row.actual_hours_logged)
            )

    for bucket in by_team.values():
        if bucket.allocated_hours > 0:
            bucket.utilization_percent = _round_hours(
                (bucket.actual_hours / bucket.allocated_hours) * Decimal("100")
            )
    return sorted(by_team.values(), key=lambda item: item.team_name)


def get_customer_by_team_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
    team_id: UUID | None = None,
) -> list[CustomerByTeamReportRow]:
    stmt = (
        select(
            Team.id,
            Team.name,
            Customer.id,
            Customer.name,
            func.count(Project.id),
        )
        .join(Project, Project.team_id == Team.id)
        .join(Customer, Project.customer_id == Customer.id)
        .where(Team.is_active.is_(True))
        .group_by(Team.id, Team.name, Customer.id, Customer.name)
        .order_by(Team.name, Customer.name)
    )
    if not include_deleted:
        stmt = stmt.where(Project.is_deleted.is_(False))
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    if team_id is not None:
        stmt = stmt.where(Team.id == team_id)

    return [
        CustomerByTeamReportRow(
            team_id=row[0],
            team_name=row[1],
            customer_id=row[2],
            customer_name=row[3],
            project_count=int(row[4] or 0),
        )
        for row in db.execute(stmt).all()
    ]


def get_designer_by_team_report(
    db: Session,
    *,
    team_id: UUID | None = None,
) -> list[DesignerByTeamReportRow]:
    stmt = (
        select(
            Team.id,
            Team.name,
            User.id,
            User.first_name,
            User.last_name,
            TeamMember.role_within_team,
        )
        .join(TeamMember, TeamMember.team_id == Team.id)
        .join(User, TeamMember.user_id == User.id)
        .where(Team.is_active.is_(True), User.is_active.is_(True))
        .order_by(Team.name, User.last_name, User.first_name)
    )
    if team_id is not None:
        stmt = stmt.where(Team.id == team_id)

    return [
        DesignerByTeamReportRow(
            team_id=row[0],
            team_name=row[1],
            user_id=row[2],
            user_name=f"{row[3]} {row[4]}".strip(),
            role_within_team=row[5],
        )
        for row in db.execute(stmt).all()
    ]


def get_team_profitability_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
    team_id: UUID | None = None,
) -> list[TeamProfitabilityReportRow]:
    rows = get_hours_by_team_report(
        db,
        include_archived=include_archived,
        include_deleted=include_deleted,
        team_id=team_id,
    )
    return [
        TeamProfitabilityReportRow(
            team_id=row.team_id,
            team_name=row.team_name,
            quoted_hours=row.quoted_hours,
            actual_hours=row.actual_hours,
            margin_hours=_round_hours(row.quoted_hours - row.actual_hours),
            margin_percent=(
                _round_hours(
                    ((row.quoted_hours - row.actual_hours) / row.quoted_hours)
                    * Decimal("100")
                )
                if row.quoted_hours > 0
                else Decimal("0.00")
            ),
        )
        for row in rows
    ]


def get_monthly_team_summary_report(
    db: Session,
    *,
    team_id: UUID | None = None,
) -> list[MonthlyTeamSummaryRow]:
    stmt = (
        select(
            Team.id,
            Team.name,
            extract("year", TimesheetEntry.entry_date),
            extract("month", TimesheetEntry.entry_date),
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(Project, TimesheetEntry.project_id == Project.id)
        .join(Team, Project.team_id == Team.id)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Team.is_active.is_(True),
            Timesheet.status == TimesheetStatus.approved,
            TimesheetEntry.work_category == WorkCategory.productive,
        )
        .group_by(Team.id, Team.name, extract("year", TimesheetEntry.entry_date), extract("month", TimesheetEntry.entry_date))
        .order_by(Team.name, extract("year", TimesheetEntry.entry_date), extract("month", TimesheetEntry.entry_date))
    )
    if team_id is not None:
        stmt = stmt.where(Team.id == team_id)

    return [
        MonthlyTeamSummaryRow(
            team_id=row[0],
            team_name=row[1],
            year=int(row[2]),
            month=int(row[3]),
            actual_hours=_round_hours(_decimal(row[4])),
        )
        for row in db.execute(stmt).all()
    ]


def get_team_resource_planning(
    db: Session,
    *,
    team_id: UUID | None = None,
    weekly_capacity_hours: Decimal = Decimal("40"),
) -> list[TeamResourcePlanningRow]:
    teams = db.scalars(
        select(Team)
        .where(Team.is_active.is_(True))
        .order_by(Team.name)
    ).all()
    if team_id is not None:
        teams = [team for team in teams if team.id == team_id]

    rows: list[TeamResourcePlanningRow] = []
    for team in teams:
        members = db.scalars(
            select(TeamMember).where(TeamMember.team_id == team.id)
        ).all()
        member_ids = [member.user_id for member in members]
        capacity = _round_hours(weekly_capacity_hours * Decimal(len(member_ids)))

        projects = db.scalars(
            select(Project).where(
                Project.team_id == team.id,
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

        allocated = Decimal("0")
        actual = Decimal("0")
        for project in projects:
            hours = calculate_hours(db, project)
            allocated += hours.quoted
            actual += hours.actual

        allocated = _round_hours(allocated)
        actual = _round_hours(actual)
        remaining = _round_hours(max(capacity - allocated, Decimal("0")))
        utilization = (
            _round_hours((actual / capacity) * Decimal("100"))
            if capacity > 0
            else Decimal("0.00")
        )

        rows.append(
            TeamResourcePlanningRow(
                team_id=team.id,
                team_name=team.name,
                team_colour=team.colour,
                member_count=len(member_ids),
                capacity_hours=capacity,
                allocated_hours=allocated,
                actual_hours=actual,
                remaining_capacity_hours=remaining,
                utilization_percent=utilization,
            )
        )
    return rows
