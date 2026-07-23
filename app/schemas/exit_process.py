"""Exit process / exit interview API schemas (PP-HRD-FO-30)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema

ExitInterviewStatus = Literal["draft", "in_progress", "completed", "cancelled"]


class ExitInterviewQuestion(BaseModel):
    id: str
    section: str
    prompt: str
    input: Literal["text", "textarea", "choice", "rating"]
    required: bool = False
    options: list[str] = Field(default_factory=list)
    min: int | None = None
    max: int | None = None
    hr_only: bool = False


class ExitInterviewCreate(BlankOptionalFieldsMixin, BaseModel):
    employee_name: str = Field(min_length=2, max_length=200)
    employee_user_id: Optional[UUID] = None
    employee_code: Optional[str] = Field(default=None, max_length=40)
    designation: Optional[str] = Field(default=None, max_length=120)
    department_name: Optional[str] = Field(default=None, max_length=120)
    org_department_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    reporting_manager_id: Optional[UUID] = None
    reporting_manager_name: Optional[str] = Field(default=None, max_length=200)
    last_working_date: Optional[date] = None
    resignation_date: Optional[date] = None
    interview_date: Optional[date] = None
    interviewer_user_id: Optional[UUID] = None
    interviewer_name: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None
    answers: dict[str, Any] = Field(default_factory=dict)


class ExitInterviewUpdate(BlankOptionalFieldsMixin, BaseModel):
    employee_name: Optional[str] = Field(default=None, max_length=200)
    employee_user_id: Optional[UUID] = None
    employee_code: Optional[str] = Field(default=None, max_length=40)
    designation: Optional[str] = Field(default=None, max_length=120)
    department_name: Optional[str] = Field(default=None, max_length=120)
    org_department_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    reporting_manager_id: Optional[UUID] = None
    reporting_manager_name: Optional[str] = Field(default=None, max_length=200)
    last_working_date: Optional[date] = None
    resignation_date: Optional[date] = None
    interview_date: Optional[date] = None
    interviewer_user_id: Optional[UUID] = None
    interviewer_name: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None
    status: Optional[ExitInterviewStatus] = None
    answers: Optional[dict[str, Any]] = None


class ExitInterviewRead(TimestampSchema):
    form_code: str
    form_title: str = "Employee Exit Interview"
    employee_user_id: Optional[UUID] = None
    employee_name: str
    employee_code: Optional[str] = None
    designation: Optional[str] = None
    department_name: Optional[str] = None
    org_department_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    team_name: Optional[str] = None
    role_id: Optional[UUID] = None
    role_name: Optional[str] = None
    reporting_manager_id: Optional[UUID] = None
    reporting_manager_name: Optional[str] = None
    last_working_date: Optional[date] = None
    resignation_date: Optional[date] = None
    interview_date: Optional[date] = None
    interviewer_user_id: Optional[UUID] = None
    interviewer_name: Optional[str] = None
    status: str
    status_label: str
    answers: dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    created_by_id: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    questions: list[ExitInterviewQuestion] = Field(default_factory=list)
