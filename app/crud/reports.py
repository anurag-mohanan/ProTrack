from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.core.non_productive_categories import (
    is_leave_entry,
    leave_entry_clause,
    standard_np_code_clause,
    standard_np_hours_clause,
)
from app.crud.base import Session
from app.crud.dashboard import get_designer_workload, _decimal, _round_hours
from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectHealth, ProjectStage, TimesheetStatus, WorkCategory
from app.models.models import Customer, Milestone, NonProductiveCode, Project, TaskType, Timesheet, TimesheetEntry, User
from app.schemas.reports import (
    BillableUtilizationReportRow,
    BillableVsNonBillableReportRow,
    CustomerSummaryReportRow,
    DesignerProductivityReportRow,
    ExecutionStatusSummaryRow,
    MilestoneCompletionReportRow,
    MonthlyNpTrendReportRow,
    NonProductiveHoursReportRow,
    NpHoursByDesignerReportRow,
    ProductiveHoursReportRow,
    ProjectDelayReportRow,
    ProjectHoursReportRow,
    ProjectPortfolioReportRow,
    ProjectStageSummaryRow,
    ReportsBundle,
    TimesheetApprovalReportRow,
    TopNpActivityReportRow,
)
from app.services.project_calculation_service import calculate_hours


def _apply_report_filters(
    stmt,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
):
    if not include_deleted:
        stmt = stmt.where(Project.is_deleted.is_(False))
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    return stmt


def get_project_hours_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
) -> list[ProjectHoursReportRow]:
    stmt = (
        select(Project, Customer.name)
        .join(Customer, Project.customer_id == Customer.id)
        .order_by(Project.tool_number)
    )
    stmt = _apply_report_filters(
        stmt, include_archived=include_archived, include_deleted=include_deleted
    )
    rows = db.execute(stmt).all()

    report: list[ProjectHoursReportRow] = []
    for project, customer_name in rows:
        hours = calculate_hours(db, project)
        report.append(
            ProjectHoursReportRow(
                project_id=project.id,
                tool_number=project.tool_number,
                part_description=project.part_description,
                customer_name=customer_name,
                quoted_hours=hours.quoted,
                actual_hours=hours.actual,
                hours_variance=hours.variance,
                execution_status=project.execution_status,
                project_stage=project.project_stage,
            )
        )
    return report


def get_customer_summary_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
) -> list[CustomerSummaryReportRow]:
    project_join = Project.customer_id == Customer.id
    if not include_deleted:
        project_join = project_join & Project.is_deleted.is_(False)
    if not include_archived:
        project_join = project_join & Project.is_archived.is_(False)
    rows = db.execute(
        select(
            Customer.id,
            Customer.name,
            func.count(Project.id),
            func.coalesce(func.sum(Project.quoted_hours), 0),
            func.coalesce(func.sum(Project.actual_hours), 0),
        )
        .outerjoin(Project, project_join)
        .group_by(Customer.id, Customer.name)
        .order_by(Customer.name)
    ).all()

    report: list[CustomerSummaryReportRow] = []
    for row in rows:
        quoted = _round_hours(_decimal(row[3]))
        actual = _round_hours(_decimal(row[4]))
        customer_id = row[0]
        project_filter = Project.customer_id == customer_id
        if not include_deleted:
            project_filter = project_filter & Project.is_deleted.is_(False)
        if not include_archived:
            project_filter = project_filter & Project.is_archived.is_(False)
        designers_used = int(
            db.scalar(
                select(func.count(func.distinct(Project.designer_id))).where(
                    project_filter,
                    Project.designer_id.is_not(None),
                )
            )
            or 0
        )
        teams_used = int(
            db.scalar(
                select(func.count(func.distinct(Project.team_id))).where(
                    project_filter,
                    Project.team_id.is_not(None),
                )
            )
            or 0
        )
        report.append(
            CustomerSummaryReportRow(
                customer_id=customer_id,
                customer_name=row[1],
                project_count=int(row[2] or 0),
                total_quoted_hours=quoted,
                total_actual_hours=actual,
                hours_variance=_round_hours(actual - quoted),
                designers_used=designers_used,
                teams_used=teams_used,
            )
        )
    return report


def get_timesheet_approval_report(db: Session) -> list[TimesheetApprovalReportRow]:
    rows = db.scalars(
        select(Timesheet).order_by(Timesheet.week_start.desc())
    ).all()
    report: list[TimesheetApprovalReportRow] = []
    for row in rows:
        owner = db.get(User, row.user_id)
        approver = db.get(User, row.approved_by) if row.approved_by else None
        total_hours = db.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                TimesheetEntry.timesheet_id == row.id
            )
        )
        report.append(
            TimesheetApprovalReportRow(
                timesheet_id=row.id,
                user_name=f"{owner.first_name} {owner.last_name}" if owner else "Unknown",
                week_start=row.week_start,
                status=row.status,
                total_hours=_round_hours(_decimal(total_hours)),
                approved_by_name=(
                    f"{approver.first_name} {approver.last_name}" if approver else None
                ),
                approval_comments=row.approval_comments,
            )
        )
    return report


def get_project_delay_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
) -> list[ProjectDelayReportRow]:
    today = date.today()
    stmt = (
        select(Project, Customer.name)
        .join(Customer, Project.customer_id == Customer.id)
        .where(
            Project.due_date < today,
            Project.execution_status != ExecutionStatus.completed,
        )
        .order_by(Project.due_date)
    )
    stmt = _apply_report_filters(
        stmt, include_archived=include_archived, include_deleted=include_deleted
    )
    rows = db.execute(stmt).all()
    report: list[ProjectDelayReportRow] = []
    for project, customer_name in rows:
        report.append(
            ProjectDelayReportRow(
                project_id=project.id,
                tool_number=project.tool_number,
                customer_name=customer_name,
                due_date=project.due_date,
                days_overdue=(today - project.due_date).days,
                health=project.health,
                execution_status=project.execution_status,
                project_stage=project.project_stage,
            )
        )
    return report


def get_milestone_completion_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
) -> list[MilestoneCompletionReportRow]:
    stmt = (
        select(Milestone, Project.code)
        .join(Project, Milestone.project_id == Project.id)
        .order_by(Project.code, Milestone.sort_order)
    )
    stmt = _apply_report_filters(
        stmt, include_archived=include_archived, include_deleted=include_deleted
    )
    rows = db.execute(stmt).all()
    return [
        MilestoneCompletionReportRow(
            project_code=code,
            milestone_name=milestone.name,
            status=milestone.status,
            due_date=milestone.due_date,
            completed_at=milestone.completed_at,
        )
        for milestone, code in rows
    ]


def get_designer_productivity_report(db: Session) -> list[DesignerProductivityReportRow]:
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    report: list[DesignerProductivityReportRow] = []
    for user in users:
        timesheets = db.scalars(
            select(Timesheet).where(Timesheet.user_id == user.id)
        ).all()
        approved = submitted = draft = Decimal("0")
        for ts in timesheets:
            hours = _decimal(
                db.scalar(
                    select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                        TimesheetEntry.timesheet_id == ts.id
                    )
                )
            )
            if ts.status == TimesheetStatus.approved:
                approved += hours
            elif ts.status == TimesheetStatus.submitted:
                submitted += hours
            elif ts.status == TimesheetStatus.draft:
                draft += hours
        role_name = user.role.name if user.role else ""
        report.append(
            DesignerProductivityReportRow(
                user_id=user.id,
                designer_name=f"{user.first_name} {user.last_name}",
                role=role_name,
                approved_hours=_round_hours(approved),
                submitted_hours=_round_hours(submitted),
                draft_hours=_round_hours(draft),
            )
        )
    return report


def get_productive_hours_report(db: Session) -> list[ProductiveHoursReportRow]:
    rows = db.execute(
        select(TimesheetEntry, Project, Customer.name, TaskType.name)
        .outerjoin(Project, TimesheetEntry.project_id == Project.id)
        .outerjoin(Customer, TimesheetEntry.customer_id == Customer.id)
        .outerjoin(TaskType, TimesheetEntry.task_type_id == TaskType.id)
        .where(TimesheetEntry.work_category == WorkCategory.productive)
    ).all()
    grouped: dict[tuple, dict] = {}
    for entry, project, customer_name, task_name in rows:
        key = (entry.project_id, entry.task_type_id)
        bucket = grouped.setdefault(
            key,
            {
                "project_id": entry.project_id,
                "tool_number": project.tool_number if project else None,
                "customer_name": customer_name,
                "task_type_name": task_name,
                "total": Decimal("0"),
                "billable": Decimal("0"),
                "non_billable": Decimal("0"),
            },
        )
        hours = _decimal(entry.hours)
        bucket["total"] += hours
        if entry.is_billable:
            bucket["billable"] += hours
        else:
            bucket["non_billable"] += hours
    return [
        ProductiveHoursReportRow(
            project_id=values["project_id"],
            tool_number=values["tool_number"],
            customer_name=values["customer_name"],
            task_type_name=values["task_type_name"],
            total_hours=_round_hours(values["total"]),
            billable_hours=_round_hours(values["billable"]),
            non_billable_hours=_round_hours(values["non_billable"]),
        )
        for values in grouped.values()
    ]


def get_non_productive_hours_report(db: Session) -> list[NonProductiveHoursReportRow]:
    rows = db.execute(
        select(TimesheetEntry, NonProductiveCode, Customer.name)
        .join(
            NonProductiveCode,
            TimesheetEntry.non_productive_code_id == NonProductiveCode.id,
        )
        .outerjoin(Customer, TimesheetEntry.customer_id == Customer.id)
        .where(
            TimesheetEntry.work_category == WorkCategory.non_productive,
            standard_np_code_clause(),
        )
    ).all()
    grouped: dict[str, dict] = {}
    for entry, np_code, customer_name in rows:
        bucket = grouped.setdefault(
            np_code.code,
            {
                "code": np_code.code,
                "description": np_code.description,
                "customer_name": customer_name,
                "total": Decimal("0"),
            },
        )
        bucket["total"] += _decimal(entry.hours)
    return [
        NonProductiveHoursReportRow(
            non_productive_code=values["code"],
            description=values["description"],
            customer_name=values["customer_name"],
            total_hours=_round_hours(values["total"]),
        )
        for values in sorted(grouped.values(), key=lambda row: row["code"])
    ]


def get_billable_utilization_report(db: Session) -> list[BillableUtilizationReportRow]:
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    report: list[BillableUtilizationReportRow] = []
    for user in users:
        entries = db.scalars(
            select(TimesheetEntry)
            .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(
                Timesheet.user_id == user.id,
                Timesheet.status == TimesheetStatus.approved,
            )
        ).all()
        billable = non_billable = np_hours = Decimal("0")
        for entry in entries:
            hours = _decimal(entry.hours)
            if entry.work_category == WorkCategory.non_productive:
                if is_leave_entry(entry):
                    continue
                np_hours += hours
            elif entry.is_billable:
                billable += hours
            else:
                non_billable += hours
        total = billable + non_billable + np_hours
        if total == 0:
            billable_pct = non_billable_pct = Decimal("0.00")
        else:
            billable_pct = _round_hours((billable / total) * Decimal("100"))
            non_billable_pct = _round_hours(((non_billable + np_hours) / total) * Decimal("100"))
        report.append(
            BillableUtilizationReportRow(
                user_id=user.id,
                designer_name=f"{user.first_name} {user.last_name}",
                billable_hours=_round_hours(billable),
                non_billable_hours=_round_hours(non_billable),
                np_hours=_round_hours(np_hours),
                billable_percent=billable_pct,
                non_billable_percent=non_billable_pct,
            )
        )
    return report


def get_monthly_np_trends_report(db: Session) -> list[MonthlyNpTrendReportRow]:
    rows = db.scalars(
        select(TimesheetEntry)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Timesheet.status == TimesheetStatus.approved,
            standard_np_hours_clause(),
        )
    ).all()
    grouped: dict[str, Decimal] = {}
    for entry in rows:
        month_key = entry.entry_date.strftime("%Y-%m")
        grouped[month_key] = grouped.get(month_key, Decimal("0")) + _decimal(entry.hours)
    return [
        MonthlyNpTrendReportRow(
            month=month,
            total_np_hours=_round_hours(total),
        )
        for month, total in sorted(grouped.items())
    ]


def get_np_hours_by_designer_report(db: Session) -> list[NpHoursByDesignerReportRow]:
    rows = db.execute(
        select(User.id, User.first_name, User.last_name, func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .join(NonProductiveCode, TimesheetEntry.non_productive_code_id == NonProductiveCode.id)
        .where(
            TimesheetEntry.work_category == WorkCategory.non_productive,
            Timesheet.status == TimesheetStatus.approved,
            standard_np_code_clause(),
        )
        .group_by(User.id, User.first_name, User.last_name)
    ).all()
    return [
        NpHoursByDesignerReportRow(
            user_id=row[0],
            designer_name=f"{row[1]} {row[2]}",
            total_np_hours=_round_hours(_decimal(row[3])),
        )
        for row in rows
        if _decimal(row[3]) > 0
    ]


def get_billable_vs_non_billable_report(db: Session) -> BillableVsNonBillableReportRow:
    entries = db.scalars(
        select(TimesheetEntry)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(Timesheet.status == TimesheetStatus.approved)
    ).all()
    billable = non_billable = np_hours = Decimal("0")
    leave_days = 0
    for entry in entries:
        hours = _decimal(entry.hours)
        if entry.work_category == WorkCategory.non_productive:
            if is_leave_entry(entry):
                leave_days += int(entry.leave_count or 0)
                continue
            np_hours += hours
        elif entry.is_billable:
            billable += hours
        else:
            non_billable += hours
    total = billable + non_billable + np_hours
    if total == 0:
        return BillableVsNonBillableReportRow(
            billable_hours=Decimal("0"),
            non_billable_hours=Decimal("0"),
            np_hours=Decimal("0"),
            leave_days=leave_days,
            billable_percent=Decimal("0.00"),
            non_billable_percent=Decimal("0.00"),
        )
    return BillableVsNonBillableReportRow(
        billable_hours=_round_hours(billable),
        non_billable_hours=_round_hours(non_billable),
        np_hours=_round_hours(np_hours),
        leave_days=leave_days,
        billable_percent=_round_hours((billable / total) * Decimal("100")),
        non_billable_percent=_round_hours(((non_billable + np_hours) / total) * Decimal("100")),
    )


def get_top_np_activities_report(db: Session, *, limit: int = 10) -> list[TopNpActivityReportRow]:
    rows = db.execute(
        select(
            NonProductiveCode.code,
            NonProductiveCode.description,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
            func.count(TimesheetEntry.id),
        )
        .join(TimesheetEntry, TimesheetEntry.non_productive_code_id == NonProductiveCode.id)
        .where(
            TimesheetEntry.work_category == WorkCategory.non_productive,
            standard_np_code_clause(),
        )
        .group_by(NonProductiveCode.code, NonProductiveCode.description)
        .order_by(func.sum(TimesheetEntry.hours).desc())
        .limit(limit)
    ).all()
    return [
        TopNpActivityReportRow(
            non_productive_code=row[0],
            description=row[1],
            total_hours=_round_hours(_decimal(row[2])),
            entry_count=int(row[3]),
        )
        for row in rows
    ]


def get_project_portfolio_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
) -> list[ProjectPortfolioReportRow]:
    stmt = (
        select(Project, Customer.name)
        .join(Customer, Project.customer_id == Customer.id)
        .order_by(Project.tool_number)
    )
    stmt = _apply_report_filters(
        stmt, include_archived=include_archived, include_deleted=include_deleted
    )
    rows = db.execute(stmt).all()
    return [
        ProjectPortfolioReportRow(
            project_id=project.id,
            tool_number=project.tool_number,
            customer_name=customer_name,
            project_stage=project.project_stage,
            execution_status=project.execution_status,
            due_date=project.due_date,
            health=project.health,
        )
        for project, customer_name in rows
    ]


def get_project_stage_summary_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
) -> list[ProjectStageSummaryRow]:
    stmt = select(Project.project_stage, func.count()).group_by(Project.project_stage)
    if not include_deleted:
        stmt = stmt.where(Project.is_deleted.is_(False))
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    rows = db.execute(stmt.order_by(Project.project_stage)).all()
    return [
        ProjectStageSummaryRow(
            project_stage=row[0],
            project_count=int(row[1] or 0),
        )
        for row in rows
    ]


def get_execution_status_summary_report(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
) -> list[ExecutionStatusSummaryRow]:
    stmt = select(Project.execution_status, func.count()).group_by(Project.execution_status)
    if not include_deleted:
        stmt = stmt.where(Project.is_deleted.is_(False))
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    rows = db.execute(stmt.order_by(Project.execution_status)).all()
    return [
        ExecutionStatusSummaryRow(
            execution_status=row[0],
            project_count=int(row[1] or 0),
        )
        for row in rows
    ]


def get_reports_bundle(
    db: Session,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
) -> ReportsBundle:
    return ReportsBundle(
        project_hours=get_project_hours_report(
            db,
            include_archived=include_archived,
            include_deleted=include_deleted,
        ),
        designer_utilization=get_designer_workload(db),
        customer_summary=get_customer_summary_report(
            db,
            include_archived=include_archived,
            include_deleted=include_deleted,
        ),
    )
