from decimal import Decimal

from sqlalchemy import func, select

from app.crud.base import Session
from app.crud.dashboard import get_designer_workload, _decimal, _round_hours
from app.models.models import Customer, Project
from app.schemas.reports import (
    CustomerSummaryReportRow,
    ProjectHoursReportRow,
    ReportsBundle,
)


def get_project_hours_report(db: Session) -> list[ProjectHoursReportRow]:
    rows = db.execute(
        select(
            Project.id,
            Project.tool_number,
            Project.part_description,
            Customer.name,
            Project.quoted_hours,
            Project.actual_hours,
            Project.status,
        )
        .join(Customer, Project.customer_id == Customer.id)
        .order_by(Project.tool_number)
    ).all()

    report: list[ProjectHoursReportRow] = []
    for row in rows:
        quoted = _round_hours(_decimal(row.quoted_hours))
        actual = _round_hours(_decimal(row.actual_hours))
        report.append(
            ProjectHoursReportRow(
                project_id=row.id,
                tool_number=row.tool_number,
                part_description=row.part_description,
                customer_name=row.name,
                quoted_hours=quoted,
                actual_hours=actual,
                hours_variance=_round_hours(actual - quoted),
                status=row.status,
            )
        )
    return report


def get_customer_summary_report(db: Session) -> list[CustomerSummaryReportRow]:
    rows = db.execute(
        select(
            Customer.id,
            Customer.name,
            func.count(Project.id),
            func.coalesce(func.sum(Project.quoted_hours), 0),
            func.coalesce(func.sum(Project.actual_hours), 0),
        )
        .outerjoin(Project, Project.customer_id == Customer.id)
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


def get_reports_bundle(db: Session) -> ReportsBundle:
    return ReportsBundle(
        project_hours=get_project_hours_report(db),
        designer_utilization=get_designer_workload(db),
        customer_summary=get_customer_summary_report(db),
    )
