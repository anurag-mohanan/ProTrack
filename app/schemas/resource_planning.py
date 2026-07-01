"""Resource planning grid — designers × time periods."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.reports import TeamResourcePlanningRow


class ResourcePlanningGranularity(str, Enum):
    day = "day"
    week = "week"
    month = "month"


class ResourceAllocationBlock(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str
    milestone_name: str | None = None
    hours: Decimal
    status_color: str


class ResourcePlanningPeriod(BaseModel):
    key: str
    label: str
    start_date: date
    end_date: date


class ResourcePlanningCell(BaseModel):
    period_key: str
    capacity_hours: Decimal
    allocated_hours: Decimal
    remaining_hours: Decimal
    status_color: str
    blocks: list[ResourceAllocationBlock] = Field(default_factory=list)


class ResourcePlanningDesignerRow(BaseModel):
    user_id: UUID
    designer_name: str
    team_name: str | None = None
    availability_status: str
    capacity_hours: Decimal
    allocated_hours: Decimal
    remaining_hours: Decimal
    cells: list[ResourcePlanningCell] = Field(default_factory=list)


class UnassignedProjectBlock(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str
    quoted_hours: Decimal
    remaining_hours: Decimal
    due_date: date
    milestone_name: str | None = None


class ResourcePlanningGrid(BaseModel):
    granularity: ResourcePlanningGranularity
    start_date: date
    end_date: date
    periods: list[ResourcePlanningPeriod] = Field(default_factory=list)
    designers: list[ResourcePlanningDesignerRow] = Field(default_factory=list)
    unassigned_projects: list[UnassignedProjectBlock] = Field(default_factory=list)
    team_summary: list[TeamResourcePlanningRow] = Field(default_factory=list)


class ResourcePlanningAssignRequest(BaseModel):
    project_id: UUID
    designer_id: UUID | None = None
