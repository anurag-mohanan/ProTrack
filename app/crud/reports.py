from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.crud.base import Session
from app.crud.dashboard import get_designer_workload, _decimal, _round_hours
from app.models.enums import MilestoneStatus, ProjectStatus, TimesheetStatus
from app.models.models import Customer, Milestone, Project, Timesheet, TimesheetEntry, User
from app.schemas.reports import (
    CustomerSummaryReportRow,
    DesignerProductivityReportRow,
    MilestoneCompletionReportRow,
    ProjectDelayReportRow,
    ProjectHoursReportRow,
    ReportsBundle,
    TimesheetApprovalReportRow,
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
                status=project.status,
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
        report.append(
            CustomerSummaryReportRow(
                customer_id=row[0],
                customer_name=row[1],
                project_count=int(row[2] or 0),
                total_quoted_hours=quoted,
                total_actual_hours=actual,
                hours_variance=_round_hours(actual - quoted),
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
            Project.status != ProjectStatus.completed,
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
                status=project.status,
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
