"""Schemas for physical workstation packages and Find Available Computer."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema


class PackageMemberIn(BlankOptionalFieldsMixin, BaseModel):
    asset_id: UUID
    role: Optional[str] = None
    is_required: bool = True
    follows_workstation: bool = True
    notes: Optional[str] = None


class WorkstationPackageCreate(BlankOptionalFieldsMixin, BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    primary_computer_asset_id: UUID
    computer_type: Optional[str] = Field(default=None, max_length=40)
    members: list[PackageMemberIn] = Field(default_factory=list)
    notes: Optional[str] = None
    effective_from: Optional[date] = None


class PackageMemberReplace(BlankOptionalFieldsMixin, BaseModel):
    old_asset_id: UUID
    new_asset_id: UUID
    reason: str = Field(min_length=1, max_length=200)
    on_date: Optional[date] = None


class PackageAssignRequest(BlankOptionalFieldsMixin, BaseModel):
    user_id: UUID
    shift_id: UUID
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    notes: Optional[str] = None
    force_override: bool = False
    override_reason: Optional[str] = Field(default=None, max_length=500)
    provisioning_request_id: Optional[UUID] = None


class PackageReturnRequest(BlankOptionalFieldsMixin, BaseModel):
    returned_date: Optional[date] = None
    notes: Optional[str] = None


class FindAvailableComputerRequest(BlankOptionalFieldsMixin, BaseModel):
    on_date: date
    shift_id: UUID
    computer_type: Optional[str] = None
    monitor_quantity: int = Field(default=0, ge=0, le=4)
    mouse_3d_required: bool = False
    user_id: Optional[UUID] = None
    provisioning_request_id: Optional[UUID] = None


class BuildPackageAndAssignRequest(BlankOptionalFieldsMixin, BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: Optional[str] = None
    primary_computer_asset_id: UUID
    computer_type: Optional[str] = None
    member_asset_ids: list[UUID] = Field(default_factory=list)
    user_id: UUID
    shift_id: UUID
    on_date: Optional[date] = None
    notes: Optional[str] = None
    provisioning_request_id: Optional[UUID] = None
