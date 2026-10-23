from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ProjectStage, TemplateSchedulingMode
from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema


class ProjectTypeBase(BaseModel):
    name: str = Field(max_length=100)
    description: str | None = None
    is_active: bool = True
    default_workstream_id: UUID | None = None


class ProjectTypeCreate(BlankOptionalFieldsMixin, ProjectTypeBase):
    pass


class ProjectTypeUpdate(BlankOptionalFieldsMixin, BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool | None = None
    default_workstream_id: UUID | None = None


class ProjectTypeRead(ProjectTypeBase, TimestampSchema):
    pass


class ProjectTemplateMilestoneBase(BaseModel):
    milestone_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    sort_order: int = 0
    default_due_offset_days: int | None = None
    is_required: bool = True
    is_visible: bool = True
    project_stage: ProjectStage | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    assigned_role: str | None = Field(default=None, max_length=100)
    default_assigned_user_id: UUID | None = None


class ProjectTemplateMilestoneCreate(BlankOptionalFieldsMixin, ProjectTemplateMilestoneBase):
    # ``id`` keeps an existing row (edit); omit it for a new milestone.
    id: UUID | None = None
    # Stable key for rows that have no id yet, so siblings can depend on them.
    client_key: str | None = Field(default=None, max_length=64)
    # Ids or client keys of sibling milestones that must finish first.
    depends_on: list[str] = Field(default_factory=list)

    @field_validator("milestone_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Milestone name is required")
        return stripped


class ProjectTemplateMilestoneUpdate(BlankOptionalFieldsMixin, BaseModel):
    milestone_name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    sort_order: int | None = None
    default_due_offset_days: int | None = None
    is_required: bool | None = None
    is_visible: bool | None = None
    project_stage: ProjectStage | None = None
    estimated_hours: Decimal | None = None
    assigned_role: str | None = Field(default=None, max_length=100)
    default_assigned_user_id: UUID | None = None


class ProjectTemplateMilestoneRead(ProjectTemplateMilestoneBase, TimestampSchema):
    project_template_id: UUID
    depends_on: list[UUID] = Field(default_factory=list)


class ProjectTemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    project_type_id: UUID
    customer_id: UUID | None = None
    default_team_id: UUID | None = None
    is_default: bool = False
    is_active: bool = True
    scheduling_mode: TemplateSchedulingMode = TemplateSchedulingMode.sequential
    revision_note: str | None = None


class ProjectTemplateCreate(BlankOptionalFieldsMixin, ProjectTemplateBase):
    milestones: list[ProjectTemplateMilestoneCreate] = Field(default_factory=list)


class ProjectTemplateUpdate(BlankOptionalFieldsMixin, BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    project_type_id: UUID | None = None
    customer_id: UUID | None = None
    default_team_id: UUID | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    scheduling_mode: TemplateSchedulingMode | None = None
    revision_note: str | None = None
    milestones: list[ProjectTemplateMilestoneCreate] | None = None


class ProjectTemplateRead(ProjectTemplateBase, TimestampSchema):
    milestone_count: int = 0
    projects_using_count: int = 0
    project_type_name: str | None = None
    customer_name: str | None = None
    template_family_id: UUID | None = None
    version: int = 1
    version_count: int = 1
    activated_at: datetime | None = None


class ProjectTemplateDetailRead(ProjectTemplateRead):
    milestones: list[ProjectTemplateMilestoneRead] = Field(default_factory=list)
    # Set when a save created a new version because projects use the old one.
    created_new_version: bool = False


class ProjectTemplateVersionRead(BaseModel):
    id: UUID
    version: int
    is_active: bool
    revision_note: str | None = None
    milestone_count: int = 0
    projects_using_count: int = 0
    created_at: datetime | None = None
    activated_at: datetime | None = None


class ProjectTemplateRevisionCreate(BaseModel):
    revision_note: str | None = None


class TemplatePreviewRequest(BaseModel):
    start_date: date
    stage_hours: dict[ProjectStage, Decimal] = Field(default_factory=dict)

    @field_validator("stage_hours")
    @classmethod
    def _non_negative(cls, value: dict[ProjectStage, Decimal]) -> dict[ProjectStage, Decimal]:
        for stage, hours in value.items():
            if hours < 0:
                raise ValueError(f"Hours for {stage.value} cannot be negative")
        return value


class TemplatePreviewMilestone(BaseModel):
    name: str
    project_stage: ProjectStage | None = None
    sort_order: int
    planned_hours: Decimal
    estimate_basis: str | None = None
    start_date: date | None = None
    finish_date: date | None = None
    depends_on: list[str] = Field(default_factory=list)


class TemplatePreviewRead(BaseModel):
    template_id: UUID
    version: int
    start_date: date
    completion_date: date | None = None
    forecast_status: str
    forecast_note: str
    milestones: list[TemplatePreviewMilestone] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProjectTemplateMatchRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    project_type_id: UUID
    customer_id: UUID | None = None
    is_default: bool
    is_customer_specific: bool = False
    customer_name: str | None = None
    default_team_id: UUID | None = None
    milestone_count: int = 0
