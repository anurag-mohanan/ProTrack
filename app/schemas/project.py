from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MilestoneStatus, ProjectHealth, ProjectStatus
from app.schemas.common import TimestampSchema


class ProjectBase(BaseModel):
    tool_number: str = Field(max_length=50)
    part_description: str = Field(max_length=255)
    customer_id: UUID
    customer_contact_id: UUID
    design_leader_id: UUID
    designer_id: UUID | None = None
    surfacer_id: UUID | None = None
    stream_id: UUID
    code: str = Field(max_length=50)
    quoted_hours: Decimal = Field(gt=0)
    due_date: date
    status: ProjectStatus = ProjectStatus.not_started
    notes: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    tool_number: str | None = Field(default=None, max_length=50)
    part_description: str | None = Field(default=None, max_length=255)
    customer_id: UUID | None = None
    customer_contact_id: UUID | None = None
    design_leader_id: UUID | None = None
    designer_id: UUID | None = None
    surfacer_id: UUID | None = None
    stream_id: UUID | None = None
    code: str | None = Field(default=None, max_length=50)
    quoted_hours: Decimal | None = Field(default=None, gt=0)
    due_date: date | None = None
    notes: str | None = None


class ProjectRead(ProjectBase, TimestampSchema):
    actual_hours: Decimal = Decimal("0")
    progress_percent: Decimal = Decimal("0.00")
    health: ProjectHealth = ProjectHealth.green


class MilestoneBase(BaseModel):
    project_id: UUID
    name: str = Field(max_length=200)
    description: str | None = None
    status: MilestoneStatus = MilestoneStatus.not_started
    due_date: date | None = None
    completed_at: datetime | None = None
    sort_order: int = 0


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"status": "completed"}},
    )

    project_id: UUID | None = None
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    status: MilestoneStatus | None = None
    due_date: date | None = None
    completed_at: datetime | None = None
    sort_order: int | None = None


class MilestoneRead(MilestoneBase, TimestampSchema):
    pass
