from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import MilestoneStatus, ProjectStage
from app.schemas.project import StageHoursInput


class StagePlanMilestone(BaseModel):
    id: UUID
    name: str
    sort_order: int
    status: MilestoneStatus
    is_required: bool = True
    original_planned_hours: Decimal | None = None
    planned_hours: Decimal
    actual_hours: Decimal
    forecast_remaining_hours: Decimal
    estimate_basis: str | None = None
    baseline_start_date: date | None = None
    baseline_finish_date: date | None = None
    forecast_start_date: date | None = None
    forecast_finish_date: date | None = None
    actual_start_date: date | None = None
    actual_finish_date: date | None = None
    due_date: date | None = None
    override_start_date: date | None = None
    override_finish_date: date | None = None
    override_reason: str | None = None
    depends_on: list[UUID] = Field(default_factory=list)
    overdue: bool = False
    forecast_late: bool = False


class StagePlanStage(BaseModel):
    key: str
    label: str
    configured: bool
    original_hours: Decimal | None = None
    current_hours: Decimal | None = None
    milestone_planned_hours: Decimal
    actual_hours: Decimal
    forecast_remaining_hours: Decimal
    eac_hours: Decimal
    variance_hours: Decimal
    variance_percent: Decimal | None = None
    allocation_mismatch: bool = False
    milestones: list[StagePlanMilestone] = Field(default_factory=list)


class EstimateRevisionRead(BaseModel):
    id: UUID
    stage: ProjectStage
    stage_label: str
    previous_hours: Decimal
    new_hours: Decimal
    reason: str
    revised_by_id: UUID | None = None
    revised_by_name: str | None = None
    revised_at: datetime


class BaselineRevisionRead(BaseModel):
    id: UUID
    revision_number: int
    previous_start_date: date | None = None
    previous_completion_date: date | None = None
    new_start_date: date | None = None
    new_completion_date: date | None = None
    reason: str
    revised_by_id: UUID | None = None
    revised_by_name: str | None = None
    revised_at: datetime


class ProjectStagePlanRead(BaseModel):
    project_id: UUID
    start_date: date | None = None
    baseline_start_date: date | None = None
    baseline_completion_date: date | None = None
    baseline_version: int = 0
    forecast_completion_date: date | None = None
    forecast_status: str | None = None
    forecast_note: str | None = None
    forecast_calculated_at: datetime | None = None
    actual_start_date: date | None = None
    actual_completion_date: date | None = None
    due_date: date | None = None
    stage_estimates_configured: bool
    original_total_hours: Decimal | None = None
    current_total_hours: Decimal | None = None
    actual_total_hours: Decimal
    forecast_remaining_hours: Decimal
    eac_hours: Decimal
    variance_hours: Decimal
    variance_percent: Decimal | None = None
    stages: list[StagePlanStage] = Field(default_factory=list)
    estimate_revisions: list[EstimateRevisionRead] = Field(default_factory=list)
    baseline_revisions: list[BaselineRevisionRead] = Field(default_factory=list)
    effort_hours_per_day: Decimal
    effort_source: str


class StageEstimatesConfigure(BaseModel):
    stage_hours: StageHoursInput


class StageEstimateRevisionCreate(BaseModel):
    stage: ProjectStage
    new_hours: Decimal = Field(ge=0)
    reason: str = Field(min_length=5, max_length=2000)

    @field_validator("reason")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 5:
            raise ValueError("Give a reason (at least 5 characters)")
        return stripped


class BaselineRevisionCreate(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)
    new_start_date: date | None = None

    @field_validator("reason")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 5:
            raise ValueError("Give a reason (at least 5 characters)")
        return stripped


class MilestoneOverrideRequest(BaseModel):
    """Set both dates to null to clear an override."""

    override_start_date: date | None = None
    override_finish_date: date | None = None
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _check(self) -> "MilestoneOverrideRequest":
        has_dates = self.override_start_date is not None or self.override_finish_date is not None
        if has_dates and not (self.reason and self.reason.strip()):
            raise ValueError("A reason is required for a schedule override")
        if (
            self.override_start_date is not None
            and self.override_finish_date is not None
            and self.override_finish_date < self.override_start_date
        ):
            raise ValueError("Override finish date cannot be before the start date")
        return self
