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


class AssetBulkActionRequest(BaseModel):
    asset_ids: list[UUID] = Field(min_length=1, max_length=2000)
    action: str = Field(
        description=(
            "delete | assign_user | assign_location | change_status | "
            "change_ownership | renumber | return_to_customer"
        )
    )
    parameters: dict = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)


class AssetBulkPreviewRequest(BaseModel):
    asset_ids: list[UUID] = Field(min_length=1, max_length=2000)
    action: str
    parameters: dict = Field(default_factory=dict)


class AssetBulkPreviewResponse(BaseModel):
    action: str
    selected: int
    asset_numbers: list[str] = Field(default_factory=list)
    dependencies: list[dict] = Field(default_factory=list)
    blocked_count: Optional[int] = None
    eligible_count: Optional[int] = None
    already_assigned: list[dict] = Field(default_factory=list)
    available: list[str] = Field(default_factory=list)
    ineligible: list[dict] = Field(default_factory=list)
    transitions: list[dict] = Field(default_factory=list)
    target_status: Optional[str] = None
    preview: list[dict] = Field(default_factory=list)
    batch_duplicates: list[str] = Field(default_factory=list)
    existing_conflicts: list[str] = Field(default_factory=list)
    can_apply: Optional[bool] = None
    warning: Optional[str] = None
    eligible: list[str] = Field(default_factory=list)


class AssetBulkActionResult(BaseModel):
    action: str
    selected: int
    updated: int
    updated_asset_numbers: list[str] = Field(default_factory=list)
    skipped: int = 0
    skipped_details: list[dict] = Field(default_factory=list)
    failed: int = 0
    failed_details: list[dict] = Field(default_factory=list)
    dependencies: list[dict] = Field(default_factory=list)
    preview: list[dict] = Field(default_factory=list)


class AssetBulkIdsResponse(BaseModel):
    ids: list[UUID]
    total: int
    truncated: bool = False


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
    assigned_to_user_id: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    assigned_to_team: Optional[str] = None
    is_open: bool = False
    assigned_date: Optional[date] = None


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
    maintenance_assets: int = 0
    open_it_requests: int = 0
    pending_onboarding_tasks: int = 0
    networks: int = 0
    allocated_ips: int = 0
    total_computers: int = 0
    assigned_computers: int = 0
    open_computers: int = 0
    available_computers: int = 0
    reserved_computers: int = 0
    maintenance_computers: int = 0
    retired_computers: int = 0
    disposed_computers: int = 0
    employees_without_computer: int = 0


class ITPersonListItem(BaseModel):
    user_id: UUID
    full_name: str
    email: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    team: Optional[str] = None
    employment_status: str
    is_active: bool = True
    has_protrack_login: bool = True
    assigned_computer_id: Optional[UUID] = None
    assigned_computer_name: Optional[str] = None
    assigned_asset_number: Optional[str] = None
    computer_status: Optional[str] = None
    other_assigned_assets: int = 0
    it_account_count: int = 0


class ITPersonDetail(BaseModel):
    user_id: UUID
    full_name: str
    email: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    team: Optional[str] = None
    employment_status: str
    is_active: bool = True
    joining_date: Optional[date] = None
    leaving_date: Optional[date] = None
    assigned_computer: Optional[dict] = None
    assigned_assets: list[dict] = Field(default_factory=list)
    accounts: list[dict] = Field(default_factory=list)
    assignment_history: list[dict] = Field(default_factory=list)


class ITResetPreview(BaseModel):
    to_delete: dict[str, int] = Field(default_factory=dict)
    session_cache_files: int = 0
    total_operational_records: int = 0
    total_including_session_files: int = 0
    will_not_delete: dict[str, int] = Field(default_factory=dict)
    preserved_notes: list[str] = Field(default_factory=list)
    confirm_phrase: str = "RESET IT DATA"
    message: str = ""


class ITResetResult(BaseModel):
    status: str
    deleted: dict[str, int] = Field(default_factory=dict)
    will_not_delete: dict[str, int] = Field(default_factory=dict)
    message: str = ""


class ComputerAssignRequest(BlankOptionalFieldsMixin, BaseModel):
    user_id: UUID
    assigned_date: Optional[date] = None
    notes: Optional[str] = None


class ComputerUnassignRequest(BlankOptionalFieldsMixin, BaseModel):
    returned_date: Optional[date] = None
    return_condition: Optional[str] = None
    notes: Optional[str] = None
    reason: Optional[str] = None


class ComputerTransferRequest(BlankOptionalFieldsMixin, BaseModel):
    to_user_id: UUID
    assigned_date: Optional[date] = None
    notes: Optional[str] = None
    reason: Optional[str] = None


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


# ---------------------------------------------------------------------------
# Sequential IT Data Import
# ---------------------------------------------------------------------------


class ITDataImportTypeStatus(BaseModel):
    id: str
    label: str
    expected_filename: str
    recommended_order: int
    depends_on: list[str] = Field(default_factory=list)
    review_only: bool = False
    canonical_sheet: str = ""
    status: str = "not_started"
    latest_batch_id: Optional[str] = None
    latest_batch_code: Optional[str] = None
    latest_committed_at: Optional[str] = None
    success_count: int = 0


class ITImportBatchRead(TimestampSchema):
    batch_code: str
    import_type: str
    filename: str
    sheet_name: Optional[str] = None
    uploaded_by_user_id: UUID
    status: str
    record_count: int = 0
    success_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    session_id: Optional[str] = None
    summary_json: Optional[str] = None
    notes: Optional[str] = None


class ITDataImportAnalyzeResult(BaseModel):
    batch_id: str
    batch_code: str
    session_id: str
    import_type: str
    filename: str
    sheet_name: str
    other_sheets: list[str] = Field(default_factory=list)
    canonical_sheet: str = ""
    review_only: bool = False
    headers: list[str] = Field(default_factory=list)
    column_bindings: dict[str, Optional[str]] = Field(default_factory=dict)
    unmapped_columns: list[str] = Field(default_factory=list)
    sensitive_columns_excluded: list[str] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)
    first_10_records: list[dict] = Field(default_factory=list)
    dependency_warnings: list[str] = Field(default_factory=list)
    fidelity_note: Optional[str] = None
    block_commit: bool = False
    commit_allowed: bool = True
    confirm_required: bool = True
    message: str = ""


class ITDataImportCommitResult(BaseModel):
    batch_id: str
    batch_code: str
    import_type: str
    filename: Optional[str] = None
    status: str = "committed"
    imported: int = 0
    skipped: int = 0
    duplicated: int = 0
    errors: list[str] = Field(default_factory=list)
    deleted: dict[str, int] = Field(default_factory=dict)
    confirm_required: bool = False
    message: str = ""
