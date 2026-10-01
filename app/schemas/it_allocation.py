"""Request bodies for the shift-aware resource allocation APIs."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BlankOptionalFieldsMixin

ResourceType = Literal["asset", "license"]


class _Window(BlankOptionalFieldsMixin, BaseModel):
    shift_id: Optional[UUID] = None
    start_time: Optional[str] = Field(default=None, max_length=5)
    end_time: Optional[str] = Field(default=None, max_length=5)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class AllocationCheckRequest(_Window):
    resource_type: ResourceType
    resource_id: UUID
    user_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    exclude_assignment_id: Optional[UUID] = None


class SetupLine(BaseModel):
    resource_type: ResourceType
    resource_id: UUID
    asset_id: Optional[UUID] = None


class SetupAssignRequest(_Window):
    user_id: UUID
    lines: list[SetupLine] = Field(min_length=1, max_length=20)
    purpose: Optional[str] = Field(default=None, max_length=200)
    assignment_type: Optional[str] = None
    allow_partial: bool = False
    dry_run: bool = False
    force_override: bool = False
    override_reason: Optional[str] = Field(default=None, max_length=500)


class ReservationCreate(_Window):
    resource_type: ResourceType
    resource_id: UUID
    user_id: Optional[UUID] = None
    reserved_for: Optional[str] = Field(default=None, max_length=200)
    provisioning_request_id: Optional[UUID] = None
    reason: Optional[str] = Field(default=None, max_length=300)
    force_override: bool = False
    override_reason: Optional[str] = Field(default=None, max_length=500)


class ReservationReleaseRequest(BlankOptionalFieldsMixin, BaseModel):
    reason: Optional[str] = Field(default=None, max_length=300)


class LicenseCheckoutRequest(BlankOptionalFieldsMixin, BaseModel):
    user_id: UUID
    asset_id: Optional[UUID] = None
    notes: Optional[str] = None


class LegacyResolveRequest(BlankOptionalFieldsMixin, BaseModel):
    mode: Literal["shift", "times", "all_hours"]
    shift_id: Optional[UUID] = None
    start_time: Optional[str] = Field(default=None, max_length=5)
    end_time: Optional[str] = Field(default=None, max_length=5)
    force_override: bool = False
    override_reason: Optional[str] = Field(default=None, max_length=500)


class SharingPolicyUpdate(BaseModel):
    is_shareable: Optional[bool] = None
    requires_shift: Optional[bool] = None
