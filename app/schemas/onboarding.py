"""Onboarding checklist API schemas (PP-HRD-FO-14)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema

OnboardingItemStatus = Literal["pending", "completed", "not_applicable"]
OnboardingChecklistStatus = Literal["in_progress", "completed", "cancelled"]


class OnboardingChecklistCreate(BlankOptionalFieldsMixin, BaseModel):
    employee_name: str = Field(min_length=2, max_length=200)
    employee_user_id: Optional[UUID] = None
    employee_code: Optional[str] = Field(default=None, max_length=40)
    joining_date: Optional[date] = None
    designation: Optional[str] = Field(default=None, max_length=120)
    department_name: Optional[str] = Field(default=None, max_length=120)
    org_department_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    reporting_manager_id: Optional[UUID] = None
    reporting_manager_name: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None
    template_id: Optional[UUID] = None


class OnboardingChecklistUpdate(BlankOptionalFieldsMixin, BaseModel):
    employee_name: Optional[str] = Field(default=None, max_length=200)
    employee_user_id: Optional[UUID] = None
    employee_code: Optional[str] = Field(default=None, max_length=40)
    joining_date: Optional[date] = None
    designation: Optional[str] = Field(default=None, max_length=120)
    department_name: Optional[str] = Field(default=None, max_length=120)
    org_department_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    reporting_manager_id: Optional[UUID] = None
    reporting_manager_name: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None
    status: Optional[OnboardingChecklistStatus] = None


class OnboardingItemStatusUpdate(BaseModel):
    status: OnboardingItemStatus
    completion_date: Optional[date] = None
    notes: Optional[str] = None


class OnboardingChecklistItemRead(TimestampSchema):
    checklist_id: UUID
    section: str
    sort_order: int
    item_text: str
    responsibility: str
    responsibility_label: str
    status: str
    status_label: str
    completed_by_id: Optional[UUID] = None
    completed_by_name: Optional[str] = None
    completion_date: Optional[date] = None
    notes: Optional[str] = None
    can_edit: bool = False


class OnboardingChecklistRead(TimestampSchema):
    template_id: Optional[UUID] = None
    template_code: Optional[str] = None
    template_name: Optional[str] = None
    employee_user_id: Optional[UUID] = None
    employee_name: str
    employee_code: Optional[str] = None
    joining_date: Optional[date] = None
    designation: Optional[str] = None
    department_name: Optional[str] = None
    org_department_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    team_name: Optional[str] = None
    role_id: Optional[UUID] = None
    role_name: Optional[str] = None
    reporting_manager_id: Optional[UUID] = None
    reporting_manager_name: Optional[str] = None
    status: str
    status_label: str
    notes: Optional[str] = None
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    completed_at: Optional[datetime] = None
    total_items: int = 0
    completed_items: int = 0
    pending_items: int = 0
    completion_percent: int = 0
    can_manage: bool = False


class OnboardingChecklistDetailRead(OnboardingChecklistRead):
    items: list[OnboardingChecklistItemRead] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)


class OnboardingTemplateRead(BaseModel):
    id: UUID
    code: str
    name: str
    version: int
    is_active: bool
