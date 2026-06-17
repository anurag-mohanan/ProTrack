from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import TimesheetStatus
from app.schemas.common import TimestampSchema


class TimesheetBase(BaseModel):
    user_id: UUID
    week_start: date
    status: TimesheetStatus = TimesheetStatus.draft
    submitted_at: datetime | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None


class TimesheetCreate(TimesheetBase):
    pass


class TimesheetUpdate(BaseModel):
    user_id: UUID | None = None
    week_start: date | None = None
    status: TimesheetStatus | None = None
    submitted_at: datetime | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None


class TimesheetRead(TimesheetBase, TimestampSchema):
    pass


class TimesheetEntryBase(BaseModel):
    timesheet_id: UUID
    project_id: UUID
    task_type_id: UUID | None = None
    milestone_id: UUID | None = None
    entry_date: date
    hours: Decimal = Field(gt=0, le=24)
    description: str | None = None


class TimesheetEntryCreate(TimesheetEntryBase):
    pass


class TimesheetEntryUpdate(BaseModel):
    timesheet_id: UUID | None = None
    project_id: UUID | None = None
    task_type_id: UUID | None = None
    milestone_id: UUID | None = None
    entry_date: date | None = None
    hours: Decimal | None = Field(default=None, gt=0, le=24)
    description: str | None = None


class TimesheetEntryRead(TimesheetEntryBase, TimestampSchema):
    pass
