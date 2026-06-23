from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ProjectHealth
from app.schemas.project import ProjectRead
from app.schemas.timesheet import TimesheetEntryRead


class DashboardSummary(BaseModel):
    total_projects: int = 0
    not_started_projects: int = 0
    in_progress_projects: int = 0
    completed_projects: int = 0
    on_hold_projects: int = 0
    total_quoted_hours: Decimal = Decimal("0")
    total_actual_hours: Decimal = Decimal("0")
    hours_variance: Decimal = Decimal("0")
    completed_milestones: int = 0
    total_milestones: int = 0
    overall_progress_percent: Decimal = Decimal("0.00")
    green_projects: int = 0
    yellow_projects: int = 0
    red_projects: int = 0


class DesignerWorkload(BaseModel):
    user_id: UUID
    designer_name: str
    role: str
    active_projects: int = 0
    hours_this_week: Decimal = Decimal("0")
    quoted_hours_assigned: Decimal = Decimal("0")
    actual_hours_logged: Decimal = Decimal("0")


class MilestoneSummary(BaseModel):
    completed: int = 0
    remaining: int = 0
    progress_percent: Decimal = Decimal("0.00")


class ProjectHoursSummary(BaseModel):
    quoted: Decimal = Decimal("0")
    actual: Decimal = Decimal("0")
    variance: Decimal = Decimal("0")


class ProjectDashboard(BaseModel):
    project: ProjectRead
    milestone_summary: MilestoneSummary
    hours: ProjectHoursSummary
    health: ProjectHealth
    recent_timesheet_entries: list[TimesheetEntryRead] = Field(default_factory=list)
