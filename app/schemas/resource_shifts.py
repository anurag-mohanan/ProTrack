"""Resource Planning shift masters, assignments, and calendar DTOs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ShiftAssignmentType(str, Enum):
    permanent = "permanent"
    rotational = "rotational"


class ShiftRotationPattern(str, Enum):
    daily = "daily"
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"
    custom = "custom"


class ShiftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    start_time: str
    end_time: str
    break_minutes: int
    is_overnight: bool
    is_active: bool
    notes: str | None = None


class ShiftCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    break_minutes: int = Field(default=60, ge=0, le=480)
    is_overnight: bool = False
    is_active: bool = True
    notes: str | None = None


class ShiftUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    start_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    break_minutes: int | None = Field(default=None, ge=0, le=480)
    is_overnight: bool | None = None
    is_active: bool | None = None
    notes: str | None = None


class ShiftAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    shift_id: UUID
    assignment_type: ShiftAssignmentType
    rotation_pattern: ShiftRotationPattern | None = None
    rotation_weekdays: list[int] = Field(default_factory=list)
    effective_from: date
    effective_to: date | None = None
    is_active: bool
    notes: str | None = None
    user_name: str | None = None
    shift_code: str | None = None
    shift_name: str | None = None


class ShiftAssignmentCreate(BaseModel):
    user_id: UUID
    shift_id: UUID
    assignment_type: ShiftAssignmentType = ShiftAssignmentType.permanent
    rotation_pattern: ShiftRotationPattern | None = None
    # 0 = Monday … 6 = Sunday. Only meaningful for rotational assignments.
    rotation_weekdays: list[int] = Field(default_factory=list)
    effective_from: date
    effective_to: date | None = None
    notes: str | None = None
    # End-date any overlapping open permanent assignment instead of rejecting.
    end_date_existing: bool = False


class ShiftAssignmentBulkCreate(BaseModel):
    user_ids: list[UUID] = Field(min_length=1)
    shift_id: UUID
    assignment_type: ShiftAssignmentType = ShiftAssignmentType.permanent
    rotation_pattern: ShiftRotationPattern | None = None
    rotation_weekdays: list[int] = Field(default_factory=list)
    effective_from: date
    effective_to: date | None = None
    notes: str | None = None
    end_date_existing: bool = False


class ShiftAssignmentEnd(BaseModel):
    effective_to: date


class ShiftAssignmentConflict(BaseModel):
    user_id: UUID
    user_name: str | None = None
    reason: str


class ShiftAssignmentBulkResult(BaseModel):
    created: list[ShiftAssignmentRead] = Field(default_factory=list)
    conflicts: list[ShiftAssignmentConflict] = Field(default_factory=list)


class ShiftForUser(BaseModel):
    user_id: UUID
    on_date: date
    shift: ShiftRead | None = None
    shift_hours: Decimal | None = None


class ShiftCalendarDay(BaseModel):
    day: date
    shift_id: UUID | None = None
    shift_code: str | None = None
    shift_name: str | None = None
    is_overnight: bool = False
    shift_hours: Decimal | None = None


class ShiftCalendarRow(BaseModel):
    user_id: UUID
    user_name: str
    team_name: str | None = None
    days: list[ShiftCalendarDay] = Field(default_factory=list)


class ShiftCalendar(BaseModel):
    start_date: date
    end_date: date
    shifts: list[ShiftRead] = Field(default_factory=list)
    rows: list[ShiftCalendarRow] = Field(default_factory=list)
