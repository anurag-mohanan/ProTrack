"""HR past employees (leavers) schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PastEmployeeRead(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    email: str
    designation: str | None = None
    joining_date: date | None = None
    leaving_date: date | None = None
    is_archived: bool = False
    is_active: bool = False
    offboard_applied_at: datetime | None = None
    has_left: bool = False
    team_names: list[str] = Field(default_factory=list)
    exit_interview_id: UUID | None = None
    attitude_was_good: bool | None = None
    skillset_rating: int | None = None
    eligible_for_rehire: str | None = None
