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
    legacy_asset_number: Optional[str] = Field(default=None, max_length=40)
    description: Optional[str] = Field(default=None, max_length=255)
    service_tag: Optional[str] = Field(default=None, max_length=100)
    purchased_by: str = Field(default="organization", max_length=40)
    owner_customer_id: Optional[UUID] = None
    customer_used_for_id: Optional[UUID] = None
    supplier_id: Optional[UUID] = None
    invoice_number: Optional[str] = Field(default=None, max_length=80)
    condition: Optional[str] = Field(default=None, max_length=40)


class AssetUpdate(BlankOptionalFieldsMixin, BaseModel):
    asset_type_id: Optional[UUID] = None
    serial_number: Optional[str] = Field(default=None, max_length=100)
    make: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(default=None, max_length=40)
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = None
    warranty_expiry: Optional[date] = None
    location: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None
    legacy_asset_number: Optional[str] = Field(default=None, max_length=40)
    description: Optional[str] = Field(default=None, max_length=255)
    service_tag: Optional[str] = Field(default=None, max_length=100)
    purchased_by: Optional[str] = Field(default=None, max_length=40)
    owner_customer_id: Optional[UUID] = None
    customer_used_for_id: Optional[UUID] = None
    supplier_id: Optional[UUID] = None
    invoice_number: Optional[str] = Field(default=None, max_length=80)
    condition: Optional[str] = Field(default=None, max_length=40)


class AssetRead(TimestampSchema):
    asset_number: str
    legacy_asset_number: Optional[str] = None
    asset_type_id: UUID
    asset_type_name: Optional[str] = None
    asset_type_code: Optional[str] = None
    description: Optional[str] = None
    serial_number: Optional[str] = None
    service_tag: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    status: str
    purchased_by: str = "organization"
    owner_customer_id: Optional[UUID] = None
    owner_customer_name: Optional[str] = None
    customer_used_for_id: Optional[UUID] = None
    customer_used_for_name: Optional[str] = None
    supplier_id: Optional[UUID] = None
    invoice_number: Optional[str] = None
    condition: Optional[str] = None
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


class AssetCustomerReturnRequest(BlankOptionalFieldsMixin, BaseModel):
    return_date: Optional[date] = None
    owner_customer_id: Optional[UUID] = None
    received_by_name: Optional[str] = Field(default=None, max_length=200)
    condition_at_return: Optional[str] = Field(default=None, max_length=40)
    return_reason: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None


class AssetCustomerReturnRead(TimestampSchema):
    asset_id: UUID
    asset_number: Optional[str] = None
    asset_type_name: Optional[str] = None
    description: Optional[str] = None
    serial_number: Optional[str] = None
    purchased_by: Optional[str] = None
    owner_customer_id: UUID
    owner_customer_name: Optional[str] = None
    return_date: date
    returned_by_user_id: UUID
    returned_by_user_name: Optional[str] = None
    received_by_name: Optional[str] = None
    condition_at_return: Optional[str] = None
    return_reason: Optional[str] = None
    notes: Optional[str] = None
    original_assignee_user_id: Optional[UUID] = None
    original_assignee_name: Optional[str] = None


class CustomerAssetReturnReportRow(BaseModel):
    id: UUID
    customer: Optional[str] = None
    asset_number: Optional[str] = None
    asset_type: Optional[str] = None
    description: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_owner: Optional[str] = None
    assigned_employee: Optional[str] = None
    return_date: date
    condition: Optional[str] = None
    returned_by: Optional[str] = None
    received_by: Optional[str] = None
    notes: Optional[str] = None
    return_reason: Optional[str] = None


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


# ---------------------------------------------------------------------------
# Data migration
# ---------------------------------------------------------------------------


class ITMigrationSourceType(BaseModel):
    id: str
    label: str
    sheet_hint: str
    description: str


class ITMigrationAnalyzeResult(BaseModel):
    session_id: str
    source_type: str
    filename: str
    sheet_name: str
    workbook_format: str = "unknown"
    column_bindings: dict[str, Optional[str]] = Field(default_factory=dict)
    records_found: int
    new_records: int
    potential_duplicates: int
    skipped_records: int
    requires_review: int
    warning_count: int = 0
    error_count: int = 0
    sensitive_columns_excluded: list[str] = Field(default_factory=list)
    sensitive_data_excluded_count: int = 0
    headers: list[str] = Field(default_factory=list)
    duplicates: list[dict] = Field(default_factory=list)
    exceptions: list[dict] = Field(default_factory=list)
    preview_rows: list[dict] = Field(default_factory=list)
    first_five_mapped: list[dict] = Field(default_factory=list)
    confirm_required: bool = True
    message: str = ""


class ITMigrationImportResult(BaseModel):
    session_id: str
    source_type: str
    filename: Optional[str] = None
    imported: int = 0
    skipped: int = 0
    duplicated: int = 0
    conflicted: int = 0
    requires_review: int = 0
    sensitive_data_excluded: int = 0
    organization_owned: int = 0
    customer_owned: int = 0
    returned_assets: int = 0
    errors: list[str] = Field(default_factory=list)
    message: str = ""
