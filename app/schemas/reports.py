from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import ProjectStatus
from app.schemas.dashboard import DesignerWorkload


class ProjectHoursReportRow(BaseModel):
    project_id: UUID
    tool_number: str
    part_description: str
    customer_name: str
    quoted_hours: Decimal
    actual_hours: Decimal
    hours_variance: Decimal
    status: ProjectStatus


class CustomerSummaryReportRow(BaseModel):
    customer_id: UUID
    customer_name: str
    project_count: int
    total_quoted_hours: Decimal
    total_actual_hours: Decimal
    hours_variance: Decimal


class ReportsBundle(BaseModel):
    project_hours: list[ProjectHoursReportRow]
    designer_utilization: list[DesignerWorkload]
    customer_summary: list[CustomerSummaryReportRow]
