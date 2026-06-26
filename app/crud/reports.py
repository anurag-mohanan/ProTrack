from decimal import Decimal

from sqlalchemy import func, select

from app.crud.base import Session
from app.crud.dashboard import get_designer_workload
from app.models.models import Customer, Project
from app.schemas.reports import (
    CustomerSummaryReportRow,
    ProjectHoursReportRow,
    ReportsBundle,
)
from app.services.project_calculation_service import calculate_hours


def get_project_hours_report(db: Session) -> list[ProjectHoursReportRow]:
    rows = db.execute(
        select(Project, Customer.name)
        .join(Customer, Project.customer_id == Customer.id)
        .order_by(Project.tool_number)
    ).all()

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
        quoted = Decimal(str(row[3] or 0)).quantize(Decimal("0.01"))
        actual = Decimal(str(row[4] or 0)).quantize(Decimal("0.01"))
        report.append(
            CustomerSummaryReportRow(
                customer_id=row[0],
                customer_name=row[1],
                project_count=int(row[2] or 0),
                total_quoted_hours=quoted,
                total_actual_hours=actual,
                hours_variance=(actual - quoted).quantize(Decimal("0.01")),
            )
        )
    return report


def get_reports_bundle(db: Session) -> ReportsBundle:
    return ReportsBundle(
        project_hours=get_project_hours_report(db),
        designer_utilization=get_designer_workload(db),
        customer_summary=get_customer_summary_report(db),
    )
