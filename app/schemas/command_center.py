from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    DecisionCategory,
    EngineeringChangeStatus,
    ExecutionStatus,
    ProjectHealth,
    ProjectPriority,
    ProjectRiskType,
    ProjectStage,
    TimelineStepStatus,
)
from app.schemas.common import TimestampSchema
from app.schemas.project import ProjectRead
from app.schemas.timesheet import TimesheetEntryRead


class ProjectFolderPaths(BaseModel):
    project_folder_path: str | None = None
    cad_folder_path: str | None = None
    released_folder_path: str | None = None
    suggested_project_folder: str | None = None
    suggested_cad_folder: str | None = None
    suggested_released_folder: str | None = None


class ProjectFolderPathsUpdate(BaseModel):
    project_folder_path: str | None = Field(default=None, max_length=500)
    cad_folder_path: str | None = Field(default=None, max_length=500)
    released_folder_path: str | None = Field(default=None, max_length=500)


class TimelineStep(BaseModel):
    milestone_id: UUID | None = None
    name: str
    sort_order: int
    status: TimelineStepStatus
    due_date: date | None = None
    completed_at: datetime | None = None


class ProjectKpis(BaseModel):
    completion_percent: Decimal
    quoted_hours: Decimal
    actual_hours: Decimal
    remaining_hours: Decimal
    variance: Decimal
    variance_percent: Decimal
    budget_consumption_percent: Decimal
    days_remaining: int
    current_milestone: str | None = None


class TeamMemberCapacity(BaseModel):
    user_id: UUID
    name: str
    role: str
    capacity_hours: Decimal
    allocated_hours: Decimal
    available_hours: Decimal
    availability_status: str


class ProjectTeamSummary(BaseModel):
    engineering_manager_name: str | None = None
    design_leader_name: str | None = None
    designer_name: str | None = None
    surfacer_name: str | None = None
    team_name: str | None = None
    team_colour: str | None = None
    members: list[TeamMemberCapacity] = Field(default_factory=list)


class CustomerProjectSummary(BaseModel):
    customer_id: UUID
    customer_name: str
    customer_code: str | None = None
    primary_contact_name: str | None = None
    primary_contact_email: str | None = None
    active_projects: int = 0
    completed_projects: int = 0
    average_hours: Decimal = Decimal("0")


class ProjectDecisionRead(TimestampSchema):
    id: UUID
    project_id: UUID
    user_id: UUID
    user_name: str | None = None
    category: DecisionCategory
    comment: str
    milestone_id: UUID | None = None
    milestone_name: str | None = None


class ProjectDecisionCreate(BaseModel):
    category: DecisionCategory = DecisionCategory.general
    comment: str = Field(min_length=1)
    milestone_id: UUID | None = None


class ProjectDecisionUpdate(BaseModel):
    category: DecisionCategory | None = None
    comment: str | None = Field(default=None, min_length=1)
    milestone_id: UUID | None = None


class EngineeringChangeRead(TimestampSchema):
    id: UUID
    project_id: UUID
    ec_number: str
    title: str
    status: EngineeringChangeStatus
    hours: Decimal
    closed_at: datetime | None = None


class EngineeringChangeCreate(BaseModel):
    ec_number: str = Field(max_length=50)
    title: str = Field(max_length=255)
    hours: Decimal = Field(default=Decimal("0"), ge=0)


class EngineeringChangeUpdate(BaseModel):
    ec_number: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=255)
    status: EngineeringChangeStatus | None = None
    hours: Decimal | None = Field(default=None, ge=0)


class EngineeringChangeSummary(BaseModel):
    open_count: int = 0
    closed_count: int = 0
    total_hours: Decimal = Decimal("0")
    items: list[EngineeringChangeRead] = Field(default_factory=list)


class ProjectRiskItem(BaseModel):
    risk_type: ProjectRiskType
    severity: str
    title: str
    detail: str | None = None


class CommandCenterHeader(BaseModel):
    tool_number: str
    part_description: str
    customer_name: str
    team_name: str | None = None
    designer_name: str | None = None
    project_stage: ProjectStage
    execution_status: ExecutionStatus
    current_milestone: str | None = None
    completion_percent: Decimal
    health: ProjectHealth
    priority: ProjectPriority
    days_remaining: int


class ProjectCommandCenter(BaseModel):
    project: ProjectRead
    header: CommandCenterHeader
    timeline: list[TimelineStep] = Field(default_factory=list)
    kpis: ProjectKpis
    team: ProjectTeamSummary
    customer_summary: CustomerProjectSummary
    decisions: list[ProjectDecisionRead] = Field(default_factory=list)
    recent_timesheets: list[TimesheetEntryRead] = Field(default_factory=list)
    engineering_changes: EngineeringChangeSummary
    risks: list[ProjectRiskItem] = Field(default_factory=list)
    folders: ProjectFolderPaths
    hours: dict[str, Decimal] = Field(default_factory=dict)
    milestone_summary: dict[str, int | Decimal] = Field(default_factory=dict)
