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
    complexity: str | None = None


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
    skill_level: str | None = None
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
    due_date: date | None = None
    milestone_name: str | None = None
    complexity: str | None = None


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


# --- IT readiness (Connected ProTrack Wave 4) ------------------------------
# Read-only projections over the IT Operations source of truth. Resource
# Planning owns no computer or software master data of its own.


class ITGapAlert(BaseModel):
    severity: str
    code: str
    message: str
    count: int = 0


class ITGapUser(BaseModel):
    user_id: UUID
    full_name: str
    email: str | None = None


class ITGapMissingSoftware(BaseModel):
    software_id: UUID
    software_name: str | None = None


class ITGapUserMissingLicenses(ITGapUser):
    missing: list[ITGapMissingSoftware] = Field(default_factory=list)


class ITLicenseDemandRow(BaseModel):
    software_id: UUID
    software_name: str | None = None
    required_headcount: int = 0
    unmet_headcount: int = 0
    seat_count: int = 0
    assigned_seats: int = 0
    available_seats: int = 0
    is_floating: bool = False
    peak_estimate: int = 0
    seat_shortfall: int = 0
    has_pool: bool = False


class ITLicensePoolRow(BaseModel):
    pool_id: UUID
    software_id: UUID
    software_name: str | None = None
    license_type: str | None = None
    is_floating: bool = False
    seat_count: int = 0
    assigned_seats: int = 0
    available_seats: int = 0
    expiry_date: date | None = None
    is_expired: bool = False
    expires_soon: bool = False


class ResourceITGaps(BaseModel):
    on_date: date
    team_id: UUID | None = None
    headcount: int = 0
    users_without_computer: list[ITGapUser] = Field(default_factory=list)
    users_missing_licenses: list[ITGapUserMissingLicenses] = Field(default_factory=list)
    license_demand: list[ITLicenseDemandRow] = Field(default_factory=list)
    oversubscribed_software: list[ITLicenseDemandRow] = Field(default_factory=list)
    software_without_pool: list[ITLicenseDemandRow] = Field(default_factory=list)
    expiring_pools: list[ITLicensePoolRow] = Field(default_factory=list)
    expired_pools: list[ITLicensePoolRow] = Field(default_factory=list)
    spare_computers: int = 0
    total_computers: int = 0
    alerts: list[ITGapAlert] = Field(default_factory=list)


class ResourceITMatrixRow(BaseModel):
    user_id: UUID
    full_name: str
    email: str | None = None
    team_name: str | None = None
    has_computer: bool = False
    computer_name: str | None = None
    asset_number: str | None = None
    required_software_count: int = 0
    licensed_software_count: int = 0
    missing_software: list[str] = Field(default_factory=list)
    is_compliant: bool = True
    is_ready: bool = False


class ResourceITMatrix(BaseModel):
    from_date: date
    to_date: date
    team_id: UUID | None = None
    headcount: int = 0
    ready_count: int = 0
    not_ready_count: int = 0
    rows: list[ResourceITMatrixRow] = Field(default_factory=list)
