from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ProjectStage
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
    milestone_name: str = Field(max_length=200)
    description: str | None = None
    sort_order: int = 0
    default_due_offset_days: int | None = None
    is_required: bool = True
    is_visible: bool = True
    project_stage: ProjectStage | None = None
    estimated_hours: Decimal | None = None
    assigned_role: str | None = Field(default=None, max_length=100)
    default_assigned_user_id: UUID | None = None


class ProjectTemplateMilestoneCreate(BlankOptionalFieldsMixin, ProjectTemplateMilestoneBase):
    pass


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


class ProjectTemplateBase(BaseModel):
    name: str = Field(max_length=200)
    description: str | None = None
    project_type_id: UUID
    customer_id: UUID | None = None
    default_team_id: UUID | None = None
    is_default: bool = False
    is_active: bool = True


class ProjectTemplateCreate(BlankOptionalFieldsMixin, ProjectTemplateBase):
    milestones: list[ProjectTemplateMilestoneCreate] = Field(default_factory=list)


class ProjectTemplateUpdate(BlankOptionalFieldsMixin, BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    project_type_id: UUID | None = None
    customer_id: UUID | None = None
    default_team_id: UUID | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    milestones: list[ProjectTemplateMilestoneCreate] | None = None


class ProjectTemplateRead(ProjectTemplateBase, TimestampSchema):
    milestone_count: int = 0
    projects_using_count: int = 0
    project_type_name: str | None = None
    customer_name: str | None = None


class ProjectTemplateDetailRead(ProjectTemplateRead):
    milestones: list[ProjectTemplateMilestoneRead] = Field(default_factory=list)


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
