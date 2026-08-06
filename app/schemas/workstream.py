"""Schemas for Workstream / ProjectWorkstream / ProjectSavedView."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ExecutionStatus, ProjectHealth, ProjectPriority
from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema


class WorkstreamBase(BaseModel):
    name: str = Field(max_length=120)
    code: str | None = Field(default=None, max_length=40)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=20)
    display_order: int = 0
    is_active: bool = True


class WorkstreamCreate(BlankOptionalFieldsMixin, WorkstreamBase):
    pass


class WorkstreamUpdate(BlankOptionalFieldsMixin, BaseModel):
    name: str | None = Field(default=None, max_length=120)
    code: str | None = Field(default=None, max_length=40)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=20)
    display_order: int | None = None
    is_active: bool | None = None


class WorkstreamRead(WorkstreamBase, TimestampSchema):
    pass


class ProjectWorkstreamBase(BaseModel):
    workstream_id: UUID
    team_id: UUID | None = None
    lead_id: UUID | None = None
    status: ExecutionStatus | None = None
    start_date: date | None = None
    due_date: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    actual_hours: Decimal | None = Field(default=None, ge=0)
    progress_percent: Decimal | None = Field(default=None, ge=0, le=100)
    health: ProjectHealth | None = None
    priority: ProjectPriority | None = None
    notes: str | None = None


class ProjectWorkstreamCreate(BlankOptionalFieldsMixin, ProjectWorkstreamBase):
    pass


class ProjectWorkstreamUpdate(BlankOptionalFieldsMixin, BaseModel):
    workstream_id: UUID | None = None
    team_id: UUID | None = None
    lead_id: UUID | None = None
    status: ExecutionStatus | None = None
    start_date: date | None = None
    due_date: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    actual_hours: Decimal | None = Field(default=None, ge=0)
    progress_percent: Decimal | None = Field(default=None, ge=0, le=100)
    health: ProjectHealth | None = None
    priority: ProjectPriority | None = None
    notes: str | None = None


class ProjectWorkstreamRead(ProjectWorkstreamBase, TimestampSchema):
    project_id: UUID
    workstream_name: str | None = None
    workstream_code: str | None = None
    team_name: str | None = None
    lead_name: str | None = None
    remaining_hours: Decimal | None = None


class ProjectWorkstreamsReplace(BaseModel):
    """Replace all workstream assignments for a project (empty list = none)."""

    items: list[ProjectWorkstreamCreate] = Field(default_factory=list)


class ProjectSavedViewBase(BaseModel):
    name: str = Field(max_length=120)
    filter_json: dict = Field(default_factory=dict)
    display_json: dict = Field(default_factory=dict)
    is_default: bool = False
    display_order: int = 0


class ProjectSavedViewCreate(BlankOptionalFieldsMixin, ProjectSavedViewBase):
    pass


class ProjectSavedViewUpdate(BlankOptionalFieldsMixin, BaseModel):
    name: str | None = Field(default=None, max_length=120)
    filter_json: dict | None = None
    display_json: dict | None = None
    is_default: bool | None = None
    display_order: int | None = None


class ProjectSavedViewRead(TimestampSchema):
    id: UUID
    user_id: UUID | None = None
    name: str
    is_system: bool = False
    filter_json: dict = Field(default_factory=dict)
    display_json: dict = Field(default_factory=dict)
    is_default: bool = False
    display_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectPortfolioSummary(BaseModel):
    active_count: int = 0
    due_week_count: int = 0
    overdue_count: int = 0
    at_risk_count: int = 0
    estimated_hours: Decimal = Decimal("0")
    actual_hours: Decimal = Decimal("0")
    remaining_hours: Decimal = Decimal("0")
