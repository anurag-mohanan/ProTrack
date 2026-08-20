"""IT Operations Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema


# ---------------------------------------------------------------------------
# Asset types
# ---------------------------------------------------------------------------


class AssetTypeCreate(BlankOptionalFieldsMixin, BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default="other", max_length=40)
    numbering_prefix: Optional[str] = Field(default=None, max_length=10)
    is_active: bool = True


class AssetTypeUpdate(BlankOptionalFieldsMixin, BaseModel):
    code: Optional[str] = Field(default=None, max_length=20)
    name: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=40)
    numbering_prefix: Optional[str] = Field(default=None, max_length=10)
    is_active: Optional[bool] = None


class AssetTypeRead(TimestampSchema):
    code: str
    name: str
    category: str
    numbering_prefix: Optional[str] = None
    is_active: bool


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


class AssetCreate(BlankOptionalFieldsMixin, BaseModel):
    asset_type_id: UUID
    serial_number: Optional[str] = Field(default=None, max_length=100)
    make: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=100)
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = None
    warranty_expiry: Optional[date] = None
    location: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None


class AssetUpdate(BlankOptionalFieldsMixin, BaseModel):
    asset_type_id: Optional[UUID] = None
    serial_number: Optional[str] = Field(default=None, max_length=100)
    make: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(default=None, max_length=20)
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = None
    warranty_expiry: Optional[date] = None
    location: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None


class AssetRead(TimestampSchema):
    asset_number: str
    asset_type_id: UUID
    asset_type_name: Optional[str] = None
    asset_type_code: Optional[str] = None
    serial_number: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    status: str
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = None
    warranty_expiry: Optional[date] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    is_deleted: bool = False
    current_assignee_id: Optional[UUID] = None
    current_assignee_name: Optional[str] = None


class AssetAssignRequest(BlankOptionalFieldsMixin, BaseModel):
    user_id: UUID
    assigned_date: Optional[date] = None
    notes: Optional[str] = None


class AssetReturnRequest(BlankOptionalFieldsMixin, BaseModel):
    returned_date: Optional[date] = None
    return_condition: Optional[str] = Field(default=None, max_length=40)
    notes: Optional[str] = None


class AssetTransferRequest(BlankOptionalFieldsMixin, BaseModel):
    to_user_id: UUID
    assigned_date: Optional[date] = None
    notes: Optional[str] = None


class AssetAssignmentRead(TimestampSchema):
    asset_id: UUID
    assigned_to_user_id: UUID
    assigned_to_user_name: Optional[str] = None
    assigned_by_user_id: UUID
    assigned_by_user_name: Optional[str] = None
    assigned_date: date
    returned_date: Optional[date] = None
    return_condition: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Computers
# ---------------------------------------------------------------------------


class ComputerCreate(BlankOptionalFieldsMixin, BaseModel):
    asset_type_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    os: Optional[str] = Field(default=None, max_length=60)
    processor: Optional[str] = Field(default=None, max_length=100)
    ram_gb: Optional[int] = Field(default=None, ge=0)
    storage_type: Optional[str] = Field(default=None, max_length=20)
    storage_gb: Optional[int] = Field(default=None, ge=0)
    domain_joined: bool = False
    mac_address: Optional[str] = Field(default=None, max_length=17)
    serial_number: Optional[str] = Field(default=None, max_length=100)
    make: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=100)
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = None
    warranty_expiry: Optional[date] = None
    location: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None


class ComputerUpdate(BlankOptionalFieldsMixin, BaseModel):
    os: Optional[str] = Field(default=None, max_length=60)
    processor: Optional[str] = Field(default=None, max_length=100)
    ram_gb: Optional[int] = Field(default=None, ge=0)
    storage_type: Optional[str] = Field(default=None, max_length=20)
    storage_gb: Optional[int] = Field(default=None, ge=0)
    domain_joined: Optional[bool] = None
    mac_address: Optional[str] = Field(default=None, max_length=17)


class ComputerRead(TimestampSchema):
    asset_id: UUID
    computer_name: str
    os: Optional[str] = None
    processor: Optional[str] = None
    ram_gb: Optional[int] = None
    storage_type: Optional[str] = None
    storage_gb: Optional[int] = None
    domain_joined: bool = False
    mac_address: Optional[str] = None
    asset_number: Optional[str] = None
    asset_type_id: Optional[UUID] = None
    asset_type_code: Optional[str] = None
    asset_type_name: Optional[str] = None
    serial_number: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None


# ---------------------------------------------------------------------------
# Networks / IPs
# ---------------------------------------------------------------------------


class NetworkCreate(BlankOptionalFieldsMixin, BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cidr: str = Field(min_length=7, max_length=18)
    gateway: Optional[str] = Field(default=None, max_length=15)
    dns_primary: Optional[str] = Field(default=None, max_length=15)
    dns_secondary: Optional[str] = Field(default=None, max_length=15)
    vlan_id: Optional[int] = None
    description: Optional[str] = None
    is_active: bool = True


class NetworkUpdate(BlankOptionalFieldsMixin, BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    gateway: Optional[str] = Field(default=None, max_length=15)
    dns_primary: Optional[str] = Field(default=None, max_length=15)
    dns_secondary: Optional[str] = Field(default=None, max_length=15)
    vlan_id: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class NetworkRead(TimestampSchema):
    name: str
    cidr: str
    gateway: Optional[str] = None
    dns_primary: Optional[str] = None
    dns_secondary: Optional[str] = None
    vlan_id: Optional[int] = None
    description: Optional[str] = None
    is_active: bool
    ip_total: int = 0
    ip_available: int = 0
    ip_allocated: int = 0


class IPAddressRead(TimestampSchema):
    network_id: UUID
    address: str
    status: str
    allocation_type: Optional[str] = None
    current_hostname: Optional[str] = None
    current_assignee_user_id: Optional[UUID] = None
    current_assignee_asset_id: Optional[UUID] = None


class IPAllocateRequest(BlankOptionalFieldsMixin, BaseModel):
    ip_address_id: Optional[UUID] = None
    network_id: Optional[UUID] = None
    assigned_to_asset_id: Optional[UUID] = None
    assigned_to_user_id: Optional[UUID] = None
    hostname: Optional[str] = Field(default=None, max_length=60)
    notes: Optional[str] = None
    allocation_type: Optional[str] = Field(default="static", max_length=20)


class IPReleaseRequest(BlankOptionalFieldsMixin, BaseModel):
    notes: Optional[str] = None


class IPAssignmentHistoryRead(TimestampSchema):
    ip_address_id: UUID
    assigned_to_asset_id: Optional[UUID] = None
    assigned_to_user_id: Optional[UUID] = None
    assigned_by_user_id: UUID
    hostname: Optional[str] = None
    assigned_date: date
    released_date: Optional[date] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Accounts / credentials
# ---------------------------------------------------------------------------


class ITUserAccountCreate(BlankOptionalFieldsMixin, BaseModel):
    user_id: UUID
    account_type: str = Field(min_length=1, max_length=40)
    username: Optional[str] = Field(default=None, max_length=120)
    display_name: Optional[str] = Field(default=None, max_length=200)
    status: str = Field(default="active", max_length=20)
    created_date: Optional[date] = None
    notes: Optional[str] = None


class ITUserAccountUpdate(BlankOptionalFieldsMixin, BaseModel):
    username: Optional[str] = Field(default=None, max_length=120)
    display_name: Optional[str] = Field(default=None, max_length=200)
    status: Optional[str] = Field(default=None, max_length=20)
    deactivated_date: Optional[date] = None
    notes: Optional[str] = None


class ITUserAccountRead(TimestampSchema):
    user_id: UUID
    account_type: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    status: str
    created_date: Optional[date] = None
    deactivated_date: Optional[date] = None
    notes: Optional[str] = None
    user_name: Optional[str] = None


class CredentialGenerateRequest(BlankOptionalFieldsMixin, BaseModel):
    user_id: UUID
    account_type: str = Field(min_length=1, max_length=40)
    username: Optional[str] = Field(default=None, max_length=120)


class CredentialGenerateResponse(BaseModel):
    account: ITUserAccountRead
    one_time_password: str


# ---------------------------------------------------------------------------
# Settings / profile / dashboard / reports
# ---------------------------------------------------------------------------


class ITSettingsRead(TimestampSchema):
    asset_numbering_pattern: str
    computer_naming_pattern: str
    default_domain: Optional[str] = None
    default_email_domain: Optional[str] = None
    ip_allocation_strategy: str
    next_asset_seq: int
    next_computer_seq: int
    settings_json: Optional[str] = None


class ITSettingsUpdate(BlankOptionalFieldsMixin, BaseModel):
    asset_numbering_pattern: Optional[str] = Field(default=None, max_length=100)
    computer_naming_pattern: Optional[str] = Field(default=None, max_length=100)
    default_domain: Optional[str] = Field(default=None, max_length=100)
    default_email_domain: Optional[str] = Field(default=None, max_length=100)
    ip_allocation_strategy: Optional[str] = Field(default=None, max_length=20)
    settings_json: Optional[str] = None


class ITProfileRead(BaseModel):
    user_id: UUID
    assets: list[AssetRead] = Field(default_factory=list)
    accounts: list[ITUserAccountRead] = Field(default_factory=list)
    ips: list[IPAddressRead] = Field(default_factory=list)


class ITDashboardSummary(BaseModel):
    total_assets: int = 0
    assigned_assets: int = 0
    available_assets: int = 0
    open_it_requests: int = 0
    pending_onboarding_tasks: int = 0
    networks: int = 0
    allocated_ips: int = 0


class AssetRegisterRow(BaseModel):
    asset_number: str
    asset_type_code: Optional[str] = None
    asset_type_name: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    status: str
    location: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = None
    warranty_expiry: Optional[date] = None
    current_assignee_name: Optional[str] = None


class IPAllocationReportRow(BaseModel):
    network_name: str
    address: str
    status: str
    hostname: Optional[str] = None
    assigned_to_user_name: Optional[str] = None
    assigned_to_asset_number: Optional[str] = None
    assigned_date: Optional[date] = None


class OpenITRequestRow(BaseModel):
    id: UUID
    ticket_number: str
    title: str
    status: str
    priority: str
    requester_name: Optional[str] = None
    assignee_name: Optional[str] = None
    created_at: Optional[datetime] = None


class PendingITOnboardingTask(BaseModel):
    item_id: UUID
    checklist_id: UUID
    item_text: str
    employee_name: str
    employee_code: Optional[str] = None
    employee_user_id: Optional[UUID] = None
    joining_date: Optional[date] = None
    help_ticket_id: Optional[UUID] = None
    owner_user_id: Optional[UUID] = None
