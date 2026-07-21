"""Schemas for dated user lifecycle actions (promotion, billing change, transfer)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PromoteRequest(BaseModel):
    new_role_id: Optional[UUID] = None
    new_designation: Optional[str] = None
    effective_date: date
    notes: Optional[str] = None


class BillingChangeRequest(BaseModel):
    new_working_model_id: Optional[UUID] = None
    effective_date: date
    notes: Optional[str] = None


class TransferRequest(BaseModel):
    target_team_id: UUID
    effective_date: date
    update_reporting_manager: bool = True


class UserJobEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    effective_date: date
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    applied_at: Optional[datetime] = None
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None


class WorkingModelPeriodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    working_model_id: Optional[UUID] = None
    working_model_name: Optional[str] = None
    effective_from: date
    effective_to: Optional[date] = None
    notes: Optional[str] = None


class UserLifecycleHistoryRead(BaseModel):
    events: list[UserJobEventRead] = Field(default_factory=list)
    working_model_periods: list[WorkingModelPeriodRead] = Field(default_factory=list)
