"""Central report data service — SQL-aggregated analytics for the reporting engine."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.non_productive_categories import is_leave_entry, leave_entry_clause, standard_np_hours_clause
from app.crud.dashboard import _decimal, _round_hours
from app.crud.foundation import get_or_create_company_settings
from app.models.enums import ExecutionStatus, MilestoneStatus, WorkCategory
from app.models.models import (
    Customer,
    Milestone,
    NonProductiveCode,
    Project,
    TaskType,
    Team,
    Timesheet,
    TimesheetEntry,
    User,
)
from app.schemas.reporting import (
    ChartSeries,
    CustomerHoursRow,
    DesignerProductivityRow,
    DesignerToolBreakdownRow,
    DetailedTimesheetRow,
    EngineeringReportPayload,
    ExecutiveKpiCard,
    ExecutiveSummary,
    FunctionHoursRow,
    LeaveAnalysisRow,
    NpAnalysisRow,
    ProjectPerformanceRow,
    QuotedVsActualRow,
    ReportPeriod,
    TeamSummaryRow,
    ToolHoursRow,
)
from app.services.holiday_service import load_holiday_dates
from app.services.project_calculation_service import calculate_hours, calculate_progress
from app.services.reporting.periods import build_report_period
from app.services.reporting.report_scope import ReportScope, user_matches_scope
from app.services.reporting.timesheet_report_inclusion import (
    users_excluded_from_timesheet_reports,
)
from app.services.kpi_participation import engineering_productivity_users


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (numerator / denominator * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _unrestricted_scope() -> ReportScope:
    return ReportScope()


def _entry_scope_clauses(scope: ReportScope):
    clauses = []
    if scope.customer_id is not None:
        # Historical imports often set Project.customer_id but leave TimesheetEntry.customer_id null.
        clauses.append(
            or_(
                TimesheetEntry.customer_id == scope.customer_id,
                TimesheetEntry.project_id.in_(
                    select(Project.id).where(Project.customer_id == scope.customer_id)
                ),
            )
        )
    if scope.user_ids is not None:
        if not scope.user_ids:
            clauses.append(Timesheet.user_id.in_(()))
        else:
            clauses.append(Timesheet.user_id.in_(tuple(scope.user_ids)))
    return clauses


def _project_scope_clauses(scope: ReportScope):
    clauses = []
    if scope.customer_id is not None:
        clauses.append(Project.customer_id == scope.customer_id)
    if scope.team_ids is not None:
        if not scope.team_ids:
            clauses.append(Project.team_id.in_(()))
        else:
            clauses.append(Project.team_id.in_(tuple(scope.team_ids)))
    return clauses


def _function_group(task_name: str | None, work_category: WorkCategory | str) -> str:
    if str(work_category) == WorkCategory.non_productive.value or work_category == WorkCategory.non_productive:
        return "Non-Productive"
    name = (task_name or "").strip().lower()
    if not name:
        return "Other"
    if "surface" in name or "polish" in name:
        return "Surfacing"
    if "feasib" in name:
        return "Feasibility"
    if "draw" in name:
        return "Drawing"
    if "bom" in name:
        return "BOM"
    if "review" in name or "check" in name:
        return "Review"
    if "meet" in name:
        return "Meetings"
    if "change" in name or name in {"ec", "ecn"}:
        return "Engineering Changes"
    if "design" in name or name in {"preliminary", "intermediate", "final"}:
        return "Design"
    return "Other"


def _tool_breakdown_bucket(task_name: str | None, work_category: WorkCategory | str) -> str:
    if str(work_category) == WorkCategory.non_productive.value or work_category == WorkCategory.non_productive:
        return "np"
    group = _function_group(task_name, work_category)
    if group == "Design":
        return "design"
    if group == "Surfacing":
        return "surfacing"
    if group == "Review":
        return "review"
    if group == "BOM":
        return "bom"
    if group == "Meetings":
        return "meetings"
    return "other"


def _entry_base_filters(start: date, end: date):
    return (
        TimesheetEntry.is_deleted.is_(False),
        TimesheetEntry.entry_date >= start,
        TimesheetEntry.entry_date <= end,
    )


def _active_designers(db: Session) -> list[User]:
    return engineering_productivity_users(db)


def build_engineering_report(
    db: Session,
    *,
    period_type: str = "monthly",
    anchor: date | None = None,
    include_archived: bool = True,
    include_deleted: bool = False,
    report_id: str | None = None,
    ai_insights: list[str] | None = None,
    scope: ReportScope | None = None,
) -> EngineeringReportPayload:
    report_scope = scope or _unrestricted_scope()
    holidays = load_holiday_dates(
        db,
        (anchor or date.today()).replace(day=1) if period_type == "monthly" else (anchor or date.today()),
        anchor or date.today(),
    )
    period = build_report_period(period_type, anchor=anchor, holidays=holidays)
    company = get_or_create_company_settings(db)
    daily_hours = _decimal(company.default_working_hours_per_day)

    designer_productivity = _designer_productivity(db, period, daily_hours, report_scope)
    designer_tool_breakdown = _designer_tool_breakdown(db, period, report_scope)
    tool_hours = _tool_hours(
        db,
        include_archived=include_archived,
        include_deleted=include_deleted,
        scope=report_scope,
    )
    customer_summary = _customer_hours(db, period, report_scope)
    team_summary = _team_summary(db, period, daily_hours, report_scope)
    function_hours = _function_hours(db, period, report_scope)
    np_analysis = _np_analysis(db, period, report_scope)
    leave_analysis = _leave_analysis(db, period, report_scope)
    quoted_vs_actual = _quoted_vs_actual(
        db,
        include_archived=include_archived,
        include_deleted=include_deleted,
        scope=report_scope,
    )
    project_performance = _project_performance(
        db,
        include_archived=include_archived,
        include_deleted=include_deleted,
        scope=report_scope,
    )
    detailed_entries = _detailed_entries(db, period, report_scope)
    executive = _executive_summary(
        db,
        period,
        company.company_name,
        designer_productivity,
        customer_summary,
        tool_hours,
        daily_hours,
    )
    charts = _build_charts(designer_productivity, customer_summary, function_hours, tool_hours)

    return EngineeringReportPayload(
        report_id=report_id or f"{period_type}-engineering",
        period=period,
        company_name=company.company_name,
        executive=executive,
        designer_productivity=designer_productivity,
        designer_tool_breakdown=designer_tool_breakdown,
        tool_hours=tool_hours,
        customer_summary=customer_summary,
        team_summary=team_summary,
        function_hours=function_hours,
        np_analysis=np_analysis,
        leave_analysis=leave_analysis,
        quoted_vs_actual=quoted_vs_actual,
        project_performance=project_performance,
        detailed_entries=detailed_entries,
        charts=charts,
        ai_insights=ai_insights or [],
    )


def _executive_summary(
    db: Session,
    period: ReportPeriod,
    company_name: str,
    designers: list[DesignerProductivityRow],
    customers: list[CustomerHoursRow],
    tools: list[ToolHoursRow],
    daily_hours: Decimal,
) -> ExecutiveSummary:
    productive = sum((row.productive_hours for row in designers), Decimal("0"))
    np_hours = sum((row.non_productive_hours for row in designers), Decimal("0"))
    leave_days = int(sum((row.leave_days for row in designers), Decimal("0")))
    total_worked = productive + np_hours
    billable = _decimal(
        db.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
            .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(
                *_entry_base_filters(period.start_date, period.end_date),
                TimesheetEntry.is_billable.is_(True),
                or_(
                    TimesheetEntry.leave_count.is_(None),
                    TimesheetEntry.leave_count <= 0,
                ),
            )
        )
    )
    team_size = len(designers)
    expected = Decimal(period.working_days) * daily_hours * Decimal(max(team_size, 1))
    utilization = _pct(total_worked, expected)
    billable_pct = _pct(billable, total_worked)

    project_filters = [Project.is_deleted.is_(False)]
    active_projects = int(db.scalar(select(func.count()).select_from(Project).where(*project_filters)) or 0)
    completed = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.execution_status == ExecutionStatus.completed,
                Project.completed_at.is_not(None),
                Project.completed_at >= period.start_date,
                Project.completed_at <= period.end_date,
            )
        )
        or 0
    )
    quoted = sum((row.quoted_hours for row in tools), Decimal("0"))
    actual = sum((row.actual_hours for row in tools), Decimal("0"))
    variance = actual - quoted

    top_tool = max(tools, key=lambda r: r.actual_hours, default=None)
    top_customer = max(customers, key=lambda r: r.total_hours, default=None)
    top_designer = max(designers, key=lambda r: r.total_hours, default=None)
    top_util = max(designers, key=lambda r: r.utilization_percent, default=None)

    kpis = [
        ExecutiveKpiCard(label="Reporting Period", value=period.label),
        ExecutiveKpiCard(label="Working Days", value=str(period.working_days)),
        ExecutiveKpiCard(label="Team Size", value=str(team_size)),
        ExecutiveKpiCard(label="Total Engineering Hours", value=str(_round_hours(total_worked))),
        ExecutiveKpiCard(label="Productive Hours", value=str(_round_hours(productive))),
        ExecutiveKpiCard(label="Non-Productive Hours", value=str(_round_hours(np_hours))),
        ExecutiveKpiCard(label="Billable %", value=f"{billable_pct}%"),
        ExecutiveKpiCard(label="Utilization %", value=f"{utilization}%"),
        ExecutiveKpiCard(label="Leave Days", value=str(leave_days)),
        ExecutiveKpiCard(label="Total Projects", value=str(active_projects)),
        ExecutiveKpiCard(label="Active Customers", value=str(len(customers))),
        ExecutiveKpiCard(label="Completed Projects", value=str(completed)),
        ExecutiveKpiCard(label="Quoted Hours", value=str(_round_hours(quoted))),
        ExecutiveKpiCard(label="Actual Hours", value=str(_round_hours(actual))),
        ExecutiveKpiCard(label="Variance", value=str(_round_hours(variance))),
        ExecutiveKpiCard(label="Most Worked Tool", value=top_tool.tool_number if top_tool else "—"),
        ExecutiveKpiCard(label="Largest Customer", value=top_customer.customer_name if top_customer else "—"),
        ExecutiveKpiCard(label="Top Performing Designer", value=top_designer.designer_name if top_designer else "—"),
        ExecutiveKpiCard(label="Highest Utilization Designer", value=top_util.designer_name if top_util else "—"),
    ]

    return ExecutiveSummary(
        period=period,
        company_name=company_name,
        kpis=kpis,
        total_engineering_hours=_round_hours(total_worked),
        productive_hours=_round_hours(productive),
        non_productive_hours=_round_hours(np_hours),
        billable_percent=billable_pct,
        utilization_percent=utilization,
        leave_days=leave_days,
        team_size=team_size,
    )


def _designer_productivity(
    db: Session,
    period: ReportPeriod,
    daily_hours: Decimal,
    scope: ReportScope,
) -> list[DesignerProductivityRow]:
    excluded = users_excluded_from_timesheet_reports(db, team_ids=scope.team_ids)
    designers = [
        person
        for person in _active_designers(db)
        if user_matches_scope(db, person, scope) and person.id not in excluded
    ]
    rows: list[DesignerProductivityRow] = []
    expected_per_person = Decimal(period.working_days) * daily_hours

    for person in designers:
        entries = db.scalars(
            select(TimesheetEntry)
            .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(
                Timesheet.user_id == person.id,
                *_entry_base_filters(period.start_date, period.end_date),
                *_entry_scope_clauses(scope),
            )
        ).all()

        productive = np_hours = leave_days = billable = Decimal("0")
        project_ids: set[UUID] = set()
        customer_ids: set[UUID] = set()
        for entry in entries:
            hours = _decimal(entry.hours)
            if is_leave_entry(entry):
                leave_days += _decimal(entry.leave_count) or Decimal("1")
                continue
            if entry.work_category == WorkCategory.non_productive:
                np_hours += hours
            else:
                productive += hours
                if entry.is_billable:
                    billable += hours
            if entry.project_id:
                project_ids.add(entry.project_id)
            if entry.customer_id:
                customer_ids.add(entry.customer_id)

        total = productive + np_hours
        team_name = None
        if person.team_id:
            team = db.get(Team, person.team_id)
            team_name = team.name if team else None

        rows.append(
            DesignerProductivityRow(
                user_id=person.id,
                designer_name=f"{person.first_name} {person.last_name}".strip(),
                team_name=team_name,
                productive_hours=_round_hours(productive),
                non_productive_hours=_round_hours(np_hours),
                leave_days=leave_days,
                total_hours=_round_hours(total),
                billable_percent=_pct(billable, total),
                utilization_percent=_pct(total, expected_per_person),
                project_count=len(project_ids),
                customer_count=len(customer_ids),
            )
        )

    return sorted(rows, key=lambda row: row.total_hours, reverse=True)


def _designer_tool_breakdown(
    db: Session, period: ReportPeriod, scope: ReportScope
) -> list[DesignerToolBreakdownRow]:
    rows = db.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            Project.id,
            Project.tool_number,
            Customer.name,
            TaskType.name,
            TimesheetEntry.work_category,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .outerjoin(Project, TimesheetEntry.project_id == Project.id)
        .outerjoin(Customer, Project.customer_id == Customer.id)
        .outerjoin(TaskType, TimesheetEntry.task_type_id == TaskType.id)
        .where(
            *_entry_base_filters(period.start_date, period.end_date),
            *_entry_scope_clauses(scope),
        )
        .group_by(
            User.id,
            User.first_name,
            User.last_name,
            Project.id,
            Project.tool_number,
            Customer.name,
            TaskType.name,
            TimesheetEntry.work_category,
        )
    ).all()

    grouped: dict[tuple, dict] = {}
    for user_id, first, last, project_id, tool, customer, task_name, category, hours in rows:
        key = (user_id, project_id, tool or "NP", customer or "—")
        bucket = grouped.setdefault(
            key,
            {
                "user_id": user_id,
                "designer_name": f"{first} {last}".strip(),
                "project_id": project_id,
                "tool_number": tool or "NP",
                "customer_name": customer or "—",
                "design": Decimal("0"),
                "surfacing": Decimal("0"),
                "review": Decimal("0"),
                "bom": Decimal("0"),
                "meetings": Decimal("0"),
                "np": Decimal("0"),
                "other": Decimal("0"),
            },
        )
        col = _tool_breakdown_bucket(task_name, category)
        bucket[col] += _decimal(hours)

    result: list[DesignerToolBreakdownRow] = []
    for values in grouped.values():
        total = sum(
            values[col] for col in ("design", "surfacing", "review", "bom", "meetings", "np", "other")
        )
        if total <= 0:
            continue
        result.append(
            DesignerToolBreakdownRow(
                user_id=values["user_id"],
                designer_name=values["designer_name"],
                tool_number=values["tool_number"],
                customer_name=values["customer_name"],
                project_id=values["project_id"],
                design_hours=_round_hours(values["design"]),
                surfacing_hours=_round_hours(values["surfacing"]),
                review_hours=_round_hours(values["review"]),
                bom_hours=_round_hours(values["bom"]),
                meeting_hours=_round_hours(values["meetings"]),
                np_hours=_round_hours(values["np"]),
                other_hours=_round_hours(values["other"]),
                total_hours=_round_hours(total),
            )
        )
    return sorted(result, key=lambda row: (row.designer_name, -row.total_hours))


def _tool_hours(
    db: Session,
    *,
    include_archived: bool,
    include_deleted: bool,
    scope: ReportScope,
) -> list[ToolHoursRow]:
    stmt = select(Project, Customer.name).join(Customer, Project.customer_id == Customer.id)
    if not include_deleted:
        stmt = stmt.where(Project.is_deleted.is_(False))
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    for clause in _project_scope_clauses(scope):
        stmt = stmt.where(clause)
    rows = db.execute(stmt.order_by(Project.tool_number)).all()

    result: list[ToolHoursRow] = []
    for project, customer_name in rows:
        hours = calculate_hours(db, project)
        progress = calculate_progress(db, project)
        quoted = hours.quoted
        actual = hours.actual
        variance_pct = _pct(actual - quoted, quoted) if quoted > 0 else Decimal("0")

        def _user_name(user_id: UUID | None) -> str | None:
            if not user_id:
                return None
            user = db.get(User, user_id)
            return f"{user.first_name} {user.last_name}".strip() if user else None

        result.append(
            ToolHoursRow(
                project_id=project.id,
                tool_number=project.tool_number,
                customer_name=customer_name,
                part_description=project.part_description or "",
                design_leader_name=_user_name(project.design_leader_id),
                designer_name=_user_name(project.designer_id),
                surfacer_name=_user_name(project.surfacer_id),
                quoted_hours=quoted,
                actual_hours=actual,
                variance_hours=hours.variance,
                variance_percent=variance_pct,
                completion_percent=progress.progress_percent,
                project_stage=project.project_stage,
                execution_status=project.execution_status,
                health=project.health,
            )
        )
    return result


def _customer_hours(db: Session, period: ReportPeriod, scope: ReportScope) -> list[CustomerHoursRow]:
    customer_link = or_(
        TimesheetEntry.customer_id == Customer.id,
        TimesheetEntry.project_id.in_(
            select(Project.id).where(Project.customer_id == Customer.id)
        ),
    )
    rows = db.execute(
        select(
            Customer.id,
            Customer.name,
            func.count(func.distinct(TimesheetEntry.project_id)),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                TimesheetEntry.work_category == WorkCategory.productive,
                                or_(
                                    TimesheetEntry.leave_count.is_(None),
                                    TimesheetEntry.leave_count <= 0,
                                ),
                            ),
                            TimesheetEntry.hours,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (standard_np_hours_clause(), TimesheetEntry.hours),
                        else_=0,
                    )
                ),
                0,
            ),
            func.count(func.distinct(Timesheet.user_id)),
        )
        .select_from(Customer)
        .join(TimesheetEntry, customer_link)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            *_entry_base_filters(period.start_date, period.end_date),
            *_entry_scope_clauses(scope),
        )
        .group_by(Customer.id, Customer.name)
    ).all()

    result: list[CustomerHoursRow] = []
    for customer_id, name, projects, productive, np_hours, designers in rows:
        productive_d = _decimal(productive)
        np_d = _decimal(np_hours)
        total = productive_d + np_d
        avg = total / Decimal(projects) if projects else Decimal("0")
        result.append(
            CustomerHoursRow(
                customer_id=customer_id,
                customer_name=name,
                project_count=int(projects or 0),
                productive_hours=_round_hours(productive_d),
                np_hours=_round_hours(np_d),
                total_hours=_round_hours(total),
                designer_count=int(designers or 0),
                avg_hours_per_project=_round_hours(avg),
            )
        )
    return sorted(result, key=lambda row: row.total_hours, reverse=True)


def _team_summary(
    db: Session,
    period: ReportPeriod,
    daily_hours: Decimal,
    scope: ReportScope,
) -> list[TeamSummaryRow]:
    teams = list(db.scalars(select(Team).order_by(Team.name)).all())
    if scope.team_ids is not None:
        teams = [team for team in teams if team.id in scope.team_ids]
    rows: list[TeamSummaryRow] = []
    for team in teams:
        members = list(
            db.scalars(
                select(User).where(
                    User.team_id == team.id,
                    User.is_active.is_(True),
                    User.is_deleted.is_(False),
                )
            ).all()
        )
        if not members:
            continue
        member_ids = [member.id for member in members]
        entries = db.scalars(
            select(TimesheetEntry)
            .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(
                Timesheet.user_id.in_(member_ids),
                *_entry_base_filters(period.start_date, period.end_date),
                *_entry_scope_clauses(scope),
            )
        ).all()
        productive = np_hours = leave_days = Decimal("0")
        project_ids: set[UUID] = set()
        for entry in entries:
            hours = _decimal(entry.hours)
            if is_leave_entry(entry):
                leave_days += _decimal(entry.leave_count) or Decimal("1")
                continue
            if entry.work_category == WorkCategory.non_productive:
                np_hours += hours
            else:
                productive += hours
            if entry.project_id:
                project_ids.add(entry.project_id)
        total = productive + np_hours
        expected = Decimal(period.working_days) * daily_hours * Decimal(len(members))
        rows.append(
            TeamSummaryRow(
                team_id=team.id,
                team_name=team.name,
                designer_count=len(members),
                project_count=len(project_ids),
                productive_hours=_round_hours(productive),
                np_hours=_round_hours(np_hours),
                leave_days=leave_days,
                total_hours=_round_hours(total),
                utilization_percent=_pct(total, expected),
            )
        )
    return sorted(rows, key=lambda row: row.total_hours, reverse=True)


def _function_hours(db: Session, period: ReportPeriod, scope: ReportScope) -> list[FunctionHoursRow]:
    stmt = (
        select(TaskType.name, TimesheetEntry.work_category, func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .outerjoin(TaskType, TimesheetEntry.task_type_id == TaskType.id)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            *_entry_base_filters(period.start_date, period.end_date),
            or_(TimesheetEntry.leave_count.is_(None), TimesheetEntry.leave_count <= 0),
            *_entry_scope_clauses(scope),
        )
        .group_by(TaskType.name, TimesheetEntry.work_category)
    )
    rows = db.execute(stmt).all()

    grouped: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for task_name, category, hours in rows:
        grouped[_function_group(task_name, category)] += _decimal(hours)

    total = sum(grouped.values(), Decimal("0"))
    order = [
        "Design",
        "Surfacing",
        "Feasibility",
        "Drawing",
        "BOM",
        "Review",
        "Meetings",
        "Engineering Changes",
        "Non-Productive",
        "Other",
    ]
    return [
        FunctionHoursRow(
            function_group=label,
            hours=_round_hours(grouped.get(label, Decimal("0"))),
            percent=_pct(grouped.get(label, Decimal("0")), total),
        )
        for label in order
        if grouped.get(label, Decimal("0")) > 0
    ]


def _np_analysis(db: Session, period: ReportPeriod, scope: ReportScope) -> list[NpAnalysisRow]:
    rows = db.execute(
        select(
            NonProductiveCode.code,
            NonProductiveCode.description,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(TimesheetEntry, TimesheetEntry.non_productive_code_id == NonProductiveCode.id)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            *_entry_base_filters(period.start_date, period.end_date),
            standard_np_hours_clause(),
            *_entry_scope_clauses(scope),
        )
        .group_by(NonProductiveCode.code, NonProductiveCode.description)
        .order_by(func.sum(TimesheetEntry.hours).desc())
    ).all()
    total = sum((_decimal(hours) for _, _, hours in rows), Decimal("0"))
    return [
        NpAnalysisRow(
            code=code,
            description=description,
            hours=_round_hours(_decimal(hours)),
            percent=_pct(_decimal(hours), total),
        )
        for code, description, hours in rows
    ]


def _leave_analysis(db: Session, period: ReportPeriod, scope: ReportScope) -> list[LeaveAnalysisRow]:
    rows = db.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            func.coalesce(func.sum(TimesheetEntry.leave_count), 0),
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .where(
            *_entry_base_filters(period.start_date, period.end_date),
            leave_entry_clause(),
            *_entry_scope_clauses(scope),
        )
        .group_by(User.id, User.first_name, User.last_name)
    ).all()
    return [
        LeaveAnalysisRow(
            user_id=user_id,
            designer_name=f"{first} {last}".strip(),
            leave_days=_decimal(days),
            leave_hours=_round_hours(_decimal(hours)),
        )
        for user_id, first, last, days, hours in rows
    ]


def _quoted_vs_actual(
    db: Session,
    *,
    include_archived: bool,
    include_deleted: bool,
    scope: ReportScope,
) -> list[QuotedVsActualRow]:
    today = date.today()
    tools = _tool_hours(
        db,
        include_archived=include_archived,
        include_deleted=include_deleted,
        scope=scope,
    )
    result: list[QuotedVsActualRow] = []
    for row in tools:
        late = int(
            db.scalar(
                select(func.count())
                .select_from(Milestone)
                .where(
                    Milestone.project_id == row.project_id,
                    Milestone.status != MilestoneStatus.completed,
                    Milestone.due_date.is_not(None),
                    Milestone.due_date < today,
                )
            )
            or 0
        )
        result.append(
            QuotedVsActualRow(
                project_id=row.project_id,
                tool_number=row.tool_number,
                customer_name=row.customer_name,
                quoted_hours=row.quoted_hours,
                actual_hours=row.actual_hours,
                variance_hours=row.variance_hours,
                variance_percent=row.variance_percent,
                completion_percent=row.completion_percent,
                health=row.health,
                late_milestones=late,
            )
        )
    return sorted(result, key=lambda row: row.variance_hours, reverse=True)


def _project_performance(
    db: Session,
    *,
    include_archived: bool,
    include_deleted: bool,
    scope: ReportScope,
) -> list[ProjectPerformanceRow]:
    tools = _tool_hours(
        db,
        include_archived=include_archived,
        include_deleted=include_deleted,
        scope=scope,
    )
    result: list[ProjectPerformanceRow] = []
    for row in tools:
        project = db.get(Project, row.project_id)
        if project is None:
            continue
        predicted = project.due_date
        result.append(
            ProjectPerformanceRow(
                project_id=row.project_id,
                tool_number=row.tool_number,
                customer_name=row.customer_name,
                designer_name=row.designer_name,
                surfacer_name=row.surfacer_name,
                project_stage=row.project_stage,
                quoted_hours=row.quoted_hours,
                actual_hours=row.actual_hours,
                milestone_completion_percent=row.completion_percent,
                health=row.health,
                predicted_finish=predicted,
            )
        )
    return result


def _detailed_entries(
    db: Session, period: ReportPeriod, scope: ReportScope
) -> list[DetailedTimesheetRow]:
    # Historical imports often leave TimesheetEntry.customer_id null while Project.customer_id is set.
    entry_customer = aliased(Customer, name="entry_customer")
    project_customer = aliased(Customer, name="project_customer")
    rows = db.execute(
        select(
            TimesheetEntry,
            User,
            Team.name,
            entry_customer.name,
            project_customer.name,
            Project.tool_number,
            TaskType.name,
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .outerjoin(Team, User.team_id == Team.id)
        .outerjoin(Project, TimesheetEntry.project_id == Project.id)
        .outerjoin(entry_customer, TimesheetEntry.customer_id == entry_customer.id)
        .outerjoin(project_customer, Project.customer_id == project_customer.id)
        .outerjoin(TaskType, TimesheetEntry.task_type_id == TaskType.id)
        .where(
            *_entry_base_filters(period.start_date, period.end_date),
            *_entry_scope_clauses(scope),
        )
        .order_by(TimesheetEntry.entry_date, User.first_name)
    ).all()

    result: list[DetailedTimesheetRow] = []
    for entry, user, team_name, entry_customer_name, project_customer_name, tool_number, task_name in rows:
        category = "Leave" if is_leave_entry(entry) else (
            "Non-Productive" if entry.work_category == WorkCategory.non_productive else "Productive"
        )
        result.append(
            DetailedTimesheetRow(
                entry_date=entry.entry_date,
                designer_name=f"{user.first_name} {user.last_name}".strip(),
                team_name=team_name,
                customer_name=entry_customer_name or project_customer_name,
                tool_number=tool_number,
                task_name=task_name,
                hours=_round_hours(_decimal(entry.hours)),
                is_billable=entry.is_billable,
                category=category,
                notes=entry.description,
            )
        )
    return result


def _build_charts(
    designers: list[DesignerProductivityRow],
    customers: list[CustomerHoursRow],
    functions: list[FunctionHoursRow],
    tools: list[ToolHoursRow],
) -> list[ChartSeries]:
    charts: list[ChartSeries] = []
    if designers:
        top = designers[:10]
        charts.append(
            ChartSeries(
                title="Top 10 Designers by Hours",
                labels=[row.designer_name for row in top],
                values=[float(row.total_hours) for row in top],
            )
        )
        charts.append(
            ChartSeries(
                title="Productive vs Non-Productive",
                labels=["Productive", "Non-Productive"],
                values=[
                    float(sum((row.productive_hours for row in designers), Decimal("0"))),
                    float(sum((row.non_productive_hours for row in designers), Decimal("0"))),
                ],
            )
        )
    if customers:
        top_customers = customers[:10]
        charts.append(
            ChartSeries(
                title="Top 10 Customers by Hours",
                labels=[row.customer_name for row in top_customers],
                values=[float(row.total_hours) for row in top_customers],
            )
        )
    if functions:
        charts.append(
            ChartSeries(
                title="Function Distribution",
                labels=[row.function_group for row in functions],
                values=[float(row.hours) for row in functions],
            )
        )
    if tools:
        over = [row for row in tools if row.quoted_hours > 0 and row.actual_hours > row.quoted_hours][:10]
        if over:
            charts.append(
                ChartSeries(
                    title="Projects Over Quote",
                    labels=[row.tool_number for row in over],
                    values=[float(row.variance_hours) for row in over],
                )
            )
    return charts
