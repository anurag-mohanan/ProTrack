from datetime import date, datetime

from decimal import Decimal

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectComplexity, ProjectHealth, ProjectPriority, ProjectStage
from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema


class ProjectWorkstreamSummary(BaseModel):
    workstream_id: UUID
    workstream_name: str | None = None
    workstream_code: str | None = None
    team_id: UUID | None = None
    team_name: str | None = None
    estimated_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    remaining_hours: Decimal | None = None
    progress_percent: Decimal | None = None


class ProjectBase(BaseModel):
    tool_number: str = Field(max_length=50)
    part_description: str = Field(max_length=255)
    customer_id: UUID
    customer_contact_id: UUID | None = None
    design_leader_id: UUID | None = None
    designer_id: UUID | None = None
    surfacer_id: UUID | None = None
    stream_id: UUID | None = None
    team_id: UUID | None = None
    code: str | None = None
    quoted_hours: Decimal = Field(default=Decimal("0"), ge=0)
    due_date: date | None = None
    project_stage: ProjectStage = ProjectStage.preliminary
    execution_status: ExecutionStatus = ExecutionStatus.planning
    priority: ProjectPriority = ProjectPriority.medium
    complexity: ProjectComplexity = ProjectComplexity.medium
    notes: str | None = None
    work_order_number: str | None = Field(default=None, max_length=100)
    press_tonnage: str | None = Field(default=None, max_length=50)
    plastic_material: str | None = Field(default=None, max_length=150)
    cavity_count: int | None = Field(default=None, ge=0)
    tool_type: str | None = Field(default=None, max_length=100)
    customer_specs: str | None = None


class ProjectCreate(BlankOptionalFieldsMixin, BaseModel):
    tool_number: str = Field(min_length=1, max_length=50)
    part_description: str = Field(min_length=1, max_length=255)
    customer_id: UUID
    customer_contact_id: UUID | None = None
    design_leader_id: UUID | None = None
    designer_id: UUID | None = None
    surfacer_id: UUID | None = None
    stream_id: UUID | None = None
    team_id: UUID | None = None
    project_type_id: UUID | None = None
    project_template_id: UUID | None = None
    working_model_id: UUID | None = None
    code: str | None = Field(default=None, max_length=50)
    quoted_hours: Decimal | None = Field(default=None, ge=0)
    due_date: date | None = None
    project_stage: ProjectStage = ProjectStage.preliminary
    execution_status: ExecutionStatus = ExecutionStatus.planning
    priority: ProjectPriority = ProjectPriority.medium
    complexity: ProjectComplexity = ProjectComplexity.medium
    notes: str | None = None
    work_order_number: str | None = Field(default=None, max_length=100)
    press_tonnage: str | None = Field(default=None, max_length=50)
    plastic_material: str | None = Field(default=None, max_length=150)
    cavity_count: int | None = Field(default=None, ge=0)
    tool_type: str | None = Field(default=None, max_length=100)
    customer_specs: str | None = None


class ProjectUpdate(BlankOptionalFieldsMixin, BaseModel):
    tool_number: str | None = Field(default=None, min_length=1, max_length=50)
    part_description: str | None = Field(default=None, max_length=255)
    customer_id: UUID | None = None
    customer_contact_id: UUID | None = None
    design_leader_id: UUID | None = None
    designer_id: UUID | None = None
    surfacer_id: UUID | None = None
    stream_id: UUID | None = None
    team_id: UUID | None = None
    project_type_id: UUID | None = None
    project_template_id: UUID | None = None
    working_model_id: UUID | None = None
    code: str | None = Field(default=None, max_length=50)
    quoted_hours: Decimal | None = Field(default=None, ge=0)
    due_date: date | None = None
    project_stage: ProjectStage | None = None
    execution_status: ExecutionStatus | None = None
    priority: ProjectPriority | None = None
    complexity: ProjectComplexity | None = None
    health: ProjectHealth | None = None
    notes: str | None = None
    work_order_number: str | None = Field(default=None, max_length=100)
    press_tonnage: str | None = Field(default=None, max_length=50)
    plastic_material: str | None = Field(default=None, max_length=150)
    cavity_count: int | None = Field(default=None, ge=0)
    tool_type: str | None = Field(default=None, max_length=100)
    customer_specs: str | None = None
    project_folder_path: str | None = Field(default=None, max_length=500)
    cad_folder_path: str | None = Field(default=None, max_length=500)
    released_folder_path: str | None = Field(default=None, max_length=500)
    qa_gate_enabled: bool | None = None


class ProjectRead(ProjectBase, TimestampSchema):
    project_type_id: UUID | None = None
    team_id: UUID | None = None
    project_template_id: UUID | None = None
    working_model_id: UUID | None = None
    actual_hours: Decimal = Decimal("0")
    current_planned_hours: Decimal = Decimal("0")
    progress_percent: Decimal = Decimal("0.00")
    health: ProjectHealth = ProjectHealth.green
    current_milestone: str | None = None
    completed_at: datetime | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    archived_by_id: UUID | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by_id: UUID | None = None
    project_folder_path: str | None = None
    cad_folder_path: str | None = None
    released_folder_path: str | None = None
    customer_name: str | None = None
    design_leader_name: str | None = None
    designer_name: str | None = None
    surfacer_name: str | None = None
    team_name: str | None = None
    project_type_name: str | None = None
    working_model_name: str | None = None
    working_model_code: str | None = None
    can_change_template: bool = True
    template_change_blocked_reason: str | None = None
    needs_setup: bool = False
    setup_gaps: list[str] = Field(default_factory=list)
    qa_gate_enabled: bool = False
    workstreams: list[ProjectWorkstreamSummary] = Field(default_factory=list)


class ProjectDeleteCheck(BaseModel):
    can_permanently_delete: bool
    blockers: list[str] = Field(default_factory=list)


class WorkorderPdfExtractResult(BaseModel):
    """Suggested workorder fields from PDF/Excel — review before saving to the project."""

    part_description: str | None = None
    work_order_number: str | None = None
    press_tonnage: str | None = None
    plastic_material: str | None = None
    cavity_count: int | None = None
    tool_type: str | None = None
    customer_specs: str | None = None
    warnings: list[str] = Field(default_factory=list)
    source_chars: int = 0


class ArchivedProjectListItem(ProjectRead):
    customer_name: str
    project_type_name: str | None = None
    design_leader_name: str | None = None


class MilestoneBase(BaseModel):
    project_id: UUID
    name: str = Field(max_length=200)
    description: str | None = None
    status: MilestoneStatus = MilestoneStatus.not_started
    due_date: date | None = None
    completed_at: datetime | None = None
    completed_date: date | None = None
    planned_hours: Decimal = Field(default=Decimal("0"), ge=0)
    progress_percent: int = Field(default=0, ge=0, le=100)
    assigned_user_id: UUID | None = None
    sort_order: int = 0


class MilestoneCreate(BlankOptionalFieldsMixin, MilestoneBase):
    pass


class MilestoneUpdate(BlankOptionalFieldsMixin, BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"status": "completed"}},
    )

    project_id: UUID | None = None
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    status: MilestoneStatus | None = None
    due_date: date | None = None
    completed_at: datetime | None = None
    completed_date: date | None = None
    planned_hours: Decimal | None = Field(default=None, ge=0)
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    assigned_user_id: UUID | None = None
    sort_order: int | None = None
    qa_acknowledged: bool | None = None


class MilestoneRead(MilestoneBase, TimestampSchema):
    actual_hours: Decimal = Decimal("0")
    assigned_user_name: str | None = None
    qa_acknowledged: bool = False
    qa_gate_required: bool = False


class MilestoneReorderItem(BaseModel):
    id: UUID
    sort_order: int


class MilestoneReorderRequest(BaseModel):
    project_id: UUID
    items: list[MilestoneReorderItem]


class ProjectMilestoneSummary(BaseModel):
    total_planned_hours: Decimal
    total_actual_hours: Decimal
    milestone_count: int
    completed_count: int
    in_progress_count: int = 0
    not_started_count: int = 0
    overall_progress_percent: int = 0
    remaining_hours: Decimal
    quoted_hours: Decimal
    current_planned_hours: Decimal
    planned_variance_hours: Decimal
