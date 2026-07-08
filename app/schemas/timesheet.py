from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ActivityAction, EntityType, NotificationType, TimesheetStatus, WorkCategory
from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema


class TimesheetApprovalRequest(BlankOptionalFieldsMixin, BaseModel):
    comments: str | None = None


class TimesheetRecalculationReport(BaseModel):
    users_checked: int
    months_recalculated: int
    entries_scanned: int
    projects_recalculated: int
    errors_fixed: int
    warnings: list[str] = Field(default_factory=list)
    execution_ms: int


class TimesheetRejectRequest(BaseModel):
    comments: str = Field(min_length=1)


class TimesheetBase(BaseModel):
    user_id: UUID
    week_start: date
    status: TimesheetStatus = TimesheetStatus.draft
    submitted_at: datetime | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    approval_comments: str | None = None


class TimesheetCreate(BaseModel):
    user_id: UUID
    week_start: date


class TimesheetUpdate(BaseModel):
    user_id: UUID | None = None
    week_start: date | None = None


class TimesheetRead(TimesheetBase, TimestampSchema):
    pass


class TimesheetEntryBase(BaseModel):
    timesheet_id: UUID
    work_category: WorkCategory = WorkCategory.productive
    project_id: UUID | None = None
    customer_id: UUID | None = None
    task_type_id: UUID | None = None
    milestone_id: UUID | None = None
    non_productive_code_id: UUID | None = None
    entry_date: date
    hours: Decimal = Field(ge=0, le=24)
    is_billable: bool = True
    leave_count: int | None = None
    description: str | None = None

    @field_validator("hours")
    @classmethod
    def validate_half_hour_increments(cls, value: Decimal) -> Decimal:
        if (value * 2) % 1 != 0:
            raise ValueError("Hours must be in 0.5 increments")
        return value


class TimesheetEntryCreate(BlankOptionalFieldsMixin, TimesheetEntryBase):
    pass


class TimesheetEntryUpdate(BlankOptionalFieldsMixin, BaseModel):
    timesheet_id: UUID | None = None
    work_category: WorkCategory | None = None
    project_id: UUID | None = None
    customer_id: UUID | None = None
    task_type_id: UUID | None = None
    milestone_id: UUID | None = None
    non_productive_code_id: UUID | None = None
    entry_date: date | None = None
    hours: Decimal | None = Field(default=None, ge=0, le=24)
    is_billable: bool | None = None
    leave_count: int | None = None
    description: str | None = None

    @field_validator("hours")
    @classmethod
    def validate_half_hour_increments(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return value
        if (value * 2) % 1 != 0:
            raise ValueError("Hours must be in 0.5 increments")
        return value


class TimesheetEntryRead(TimesheetEntryBase, TimestampSchema):
    project_tool_number: str | None = None
    project_code: str | None = None
    customer_name: str | None = None
    task_type_name: str | None = None
    milestone_name: str | None = None
    non_productive_code: str | None = None
    non_productive_description: str | None = None
    non_productive_category: str | None = None
    user_id: UUID | None = None
    user_name: str | None = None


class TimesheetEntryBulkUpsert(BaseModel):
    id: UUID | None = None
    timesheet_id: UUID
    work_category: WorkCategory = WorkCategory.productive
    project_id: UUID | None = None
    customer_id: UUID | None = None
    task_type_id: UUID | None = None
    milestone_id: UUID | None = None
    non_productive_code_id: UUID | None = None
    entry_date: date
    hours: Decimal = Field(ge=0, le=24)
    is_billable: bool = True
    leave_count: int | None = None
    description: str | None = None

    @field_validator("hours")
    @classmethod
    def validate_half_hour_increments(cls, value: Decimal) -> Decimal:
        if (value * 2) % 1 != 0:
            raise ValueError("Hours must be in 0.5 increments")
        return value


class TimesheetEntryBulkRequest(BaseModel):
    upserts: list[TimesheetEntryBulkUpsert] = Field(default_factory=list)
    deletes: list[UUID] = Field(default_factory=list)


class TimesheetEntryBulkResponse(BaseModel):
    upserted: list[TimesheetEntryRead]
    deleted: list[UUID]


class TimesheetEntryDeletionLogRead(TimestampSchema):
    id: UUID
    entry_id: UUID
    designer_user_id: UUID
    designer_name: str
    entry_date: date
    tool_number: str | None = None
    task_name: str | None = None
    hours: Decimal
    is_billable: bool
    notes: str | None = None
    deleted_by_id: UUID
    deleted_by_name: str | None = None
    deleted_at: datetime
    reason: str
    restored_at: datetime | None = None
    restored_by_id: UUID | None = None


class ActivityRead(TimestampSchema):
    id: UUID
    user_id: UUID | None = None
    user_name: str | None = None
    entity_type: EntityType
    entity_id: UUID
    action: ActivityAction
    old_value: str | None = None
    new_value: str | None = None


class NotificationRead(TimestampSchema):
    id: UUID
    user_id: UUID
    notification_type: NotificationType
    title: str
    message: str
    entity_type: EntityType | None = None
    entity_id: UUID | None = None
    is_read: bool
    read_at: datetime | None = None


class NotificationSummary(BaseModel):
    unread_count: int
