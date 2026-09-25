"""Schemas for IT employee provisioning / onboarding IT requests."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema


class ProvisioningHardwareIn(BlankOptionalFieldsMixin, BaseModel):
    computer_required: bool = True
    computer_type: Optional[str] = Field(default=None, max_length=40)
    computer_is_required: bool = True
    monitor_quantity: Optional[int] = Field(default=None, ge=0, le=4)
    monitor_is_required: bool = True
    mouse_3d_required: bool = False
    mouse_3d_is_required: bool = False
    mouse_3d_model_hint: Optional[str] = Field(default=None, max_length=200)
    mouse_3d_asset_type_id: Optional[UUID] = None
    wireless_mouse_required: Optional[bool] = None
    laptop_dock_required: bool = False
    laptop_bag_required: bool = False
    headset_required: bool = False
    wireless_keyboard_required: bool = False


class ProvisioningSoftwareLineIn(BlankOptionalFieldsMixin, BaseModel):
    software_id: UUID
    requirement_level: str = "required"
    license_required: bool = True
    version: Optional[str] = Field(default=None, max_length=80)
    purpose: Optional[str] = Field(default=None, max_length=500)
    priority: Optional[str] = Field(default=None, max_length=20)
    reason: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None


class HireWithItRequest(BlankOptionalFieldsMixin, BaseModel):
    """Create user + IT provisioning in one call (Admin/HR)."""

    # Nested user create fields are accepted via user payload
    user: dict
    shift_id: Optional[UUID] = None
    hardware: ProvisioningHardwareIn = Field(default_factory=ProvisioningHardwareIn)
    software: list[ProvisioningSoftwareLineIn] = Field(default_factory=list, max_length=5)
    required_by: Optional[date] = None
    priority: str = "medium"
    notes: Optional[str] = None
    create_checklist: bool = True


class ProvisioningForExistingUserRequest(BlankOptionalFieldsMixin, BaseModel):
    user_id: UUID
    shift_id: Optional[UUID] = None
    hardware: ProvisioningHardwareIn = Field(default_factory=ProvisioningHardwareIn)
    software: list[ProvisioningSoftwareLineIn] = Field(default_factory=list, max_length=5)
    required_by: Optional[date] = None
    priority: str = "medium"
    notes: Optional[str] = None
    checklist_id: Optional[UUID] = None


class ProvisioningHardwareRead(TimestampSchema):
    provisioning_request_id: UUID
    computer_required: bool
    computer_type: Optional[str] = None
    computer_type_label: Optional[str] = None
    computer_is_required: bool
    monitor_quantity: int
    monitor_is_required: bool
    mouse_3d_required: bool
    mouse_3d_is_required: bool
    mouse_3d_model_hint: Optional[str] = None
    mouse_3d_asset_type_id: Optional[UUID] = None
    wireless_mouse_required: bool
    laptop_dock_required: bool
    laptop_bag_required: bool
    headset_required: bool
    wireless_keyboard_required: bool


class ProvisioningSoftwareRead(TimestampSchema):
    user_id: UUID
    software_id: UUID
    software_name: Optional[str] = None
    requirement_level: str
    license_required: bool = True
    priority: str = "medium"
    purpose: Optional[str] = None
    version: Optional[str] = None
    status: str
    requested_by_id: Optional[UUID] = None
    provisioning_request_id: Optional[UUID] = None


class ProvisioningRequestRead(TimestampSchema):
    user_id: UUID
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    joining_date: Optional[date] = None
    checklist_id: Optional[UUID] = None
    ticket_id: Optional[UUID] = None
    ticket_number: Optional[str] = None
    shift_id: Optional[UUID] = None
    shift_display: Optional[str] = None
    required_by: Optional[date] = None
    priority: str
    status: str
    assigned_it_user_id: Optional[UUID] = None
    assigned_it_user_name: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    is_overdue: bool = False
    hardware: Optional[ProvisioningHardwareRead] = None
    software: list[ProvisioningSoftwareRead] = Field(default_factory=list)


class ProvisioningStatusUpdate(BlankOptionalFieldsMixin, BaseModel):
    status: str
    assigned_it_user_id: Optional[UUID] = None
    notes: Optional[str] = None


class ProvisioningHardwareUpdate(BlankOptionalFieldsMixin, BaseModel):
    hardware: ProvisioningHardwareIn
    reason: Optional[str] = Field(default=None, max_length=500)


class SoftwareRequirementStatusUpdate(BlankOptionalFieldsMixin, BaseModel):
    status: str


class OnboardingReadinessRead(BaseModel):
    user_id: str
    overall: str
    items: list[dict] = Field(default_factory=list)
    required_count: int = 0
    done_required_count: int = 0
    provisioning_request_id: Optional[str] = None


class ProvisioningDashboardRead(BaseModel):
    new_employee_requests: int = 0
    open_it_requests: int = 0
    due_today: int = 0
    overdue_requests: int = 0
    waiting_for_hardware: int = 0
    waiting_for_software_license: int = 0
    ready_for_joining: int = 0
    completed: int = 0
    hardware_demand: dict = Field(default_factory=dict)
    software_demand: list[dict] = Field(default_factory=list)


class Employee360Read(BaseModel):
    overview: dict = Field(default_factory=dict)
    employment: dict = Field(default_factory=dict)
    shift: Optional[dict] = None
    it_assets: list[dict] = Field(default_factory=list)
    workstation_packages: list[dict] = Field(default_factory=list)
    virtual_seats: list[dict] = Field(default_factory=list)
    consumables: list[dict] = Field(default_factory=list)
    software_licenses: list[dict] = Field(default_factory=list)
    performance_reviews: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    timesheets: dict = Field(default_factory=dict)
    onboarding: Optional[OnboardingReadinessRead] = None
