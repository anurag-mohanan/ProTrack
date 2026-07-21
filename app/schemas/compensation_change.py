"""Schemas for compensation change requests (hike / promotion with 2-level approval)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CompensationChangeCreate(BaseModel):
    user_id: UUID
    request_type: str = Field(default="hike", pattern="^(hike|promotion)$")
    hike_pct: Optional[Decimal] = None
    effective_date: date
    justification: Optional[str] = None
    new_role_id: Optional[UUID] = None
    new_designation: Optional[str] = None
    new_working_model_id: Optional[UUID] = None


class CompensationChangeWorkflowAction(BaseModel):
    action: str = Field(pattern="^(approve-l1|approve-l2|reject|withdraw)$")
    rejection_reason: Optional[str] = None


class CompensationChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    employee_name: Optional[str] = None
    request_type: str
    stage: str
    status: str
    suggested_by_id: Optional[UUID] = None
    suggested_by_name: Optional[str] = None
    hike_pct: Optional[Decimal] = None
    currency_code: str
    current_monthly_salary: Optional[Decimal] = None
    proposed_monthly_salary: Optional[Decimal] = None
    new_role_id: Optional[UUID] = None
    new_role_name: Optional[str] = None
    new_designation: Optional[str] = None
    new_working_model_id: Optional[UUID] = None
    new_working_model_name: Optional[str] = None
    effective_date: date
    justification: Optional[str] = None
    l1_approver_id: Optional[UUID] = None
    l1_approver_name: Optional[str] = None
    l1_at: Optional[datetime] = None
    l2_approver_id: Optional[UUID] = None
    l2_approver_name: Optional[str] = None
    l2_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    can_approve_l1: bool = False
    can_approve_l2: bool = False
    can_withdraw: bool = False
