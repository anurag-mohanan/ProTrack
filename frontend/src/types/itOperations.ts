export type AssetStatus =
  | 'available'
  | 'assigned'
  | 'maintenance'
  | 'awaiting_return'
  | 'returned_to_customer'
  | 'lost'
  | 'damaged'
  | 'retired'
  | 'disposed';

export type PurchasedBy =
  | 'organization'
  | 'customer'
  | 'vendor'
  | 'leased'
  | 'other'
  | 'unknown'
  | string;

export type AssetTypeCategory =
  | 'computer'
  | 'peripheral'
  | 'network_equipment'
  | 'other'
  | string;

export type IpStatus = 'available' | 'allocated' | 'reserved' | 'disabled' | string;

export type ReturnCondition = 'good' | 'damaged' | 'needs_repair' | string;

export type IpAllocationStrategy = 'sequential' | 'manual' | string;

export interface ITDashboardSummary {
  total_assets: number;
  available_assets: number;
  assigned_assets: number;
  maintenance_assets?: number;
  open_it_requests: number;
  networks: number;
  allocated_ips: number;
  pending_onboarding_tasks: number;
  total_computers?: number;
  assigned_computers?: number;
  open_computers?: number;
  available_computers?: number;
  reserved_computers?: number;
  maintenance_computers?: number;
  retired_computers?: number;
  disposed_computers?: number;
  employees_without_computer?: number;
  software_catalog_count?: number;
  active_software_count?: number;
  license_pool_count?: number;
  software_assignments_count?: number;
  licenses_expiring_30?: number;
  licenses_expired?: number;
}

export interface AssetType {
  id: string;
  code: string;
  name: string;
  category: AssetTypeCategory;
  is_active: boolean;
  numbering_prefix?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface AssetTypeCreate {
  code: string;
  name: string;
  category?: AssetTypeCategory;
  is_active?: boolean;
  numbering_prefix?: string | null;
}

export interface AssetTypeUpdate {
  code?: string;
  name?: string;
  category?: AssetTypeCategory;
  is_active?: boolean;
  numbering_prefix?: string | null;
}

export interface ITAssetCategory {
  id: string;
  code: string;
  name: string;
  is_active?: boolean;
  notes?: string | null;
  usage_count?: number;
}

export interface AssetMake {
  id: string;
  name: string;
  is_active?: boolean;
  notes?: string | null;
  usage_count?: number;
}

export interface AssetMakeCreate {
  name: string;
  asset_type_id?: string | null;
}

export interface AssetModel {
  id: string;
  name: string;
  make_id: string;
  asset_type_id: string;
  is_active?: boolean;
  notes?: string | null;
  usage_count?: number;
}

export interface AssetModelCreate {
  name: string;
  make_id: string;
  asset_type_id: string;
}

export interface ITSupplier {
  id: string;
  name: string;
  website?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  products?: string | null;
  notes?: string | null;
  is_active?: boolean;
  usage_count?: number;
}

export interface ITSupplierCreate {
  name: string;
  website?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  notes?: string | null;
}

export interface NextAssetNumberPreview {
  asset_number: string;
  prefix?: string;
  sequence?: number;
}

export interface NextAssetNumbersPreview {
  asset_type_id: string;
  count: number;
  asset_numbers: string[];
  message?: string;
}

export type MasterKind = 'categories' | 'types' | 'makes' | 'models' | 'suppliers';

export interface MasterMergeResult {
  source_id: string;
  source_name: string;
  target_id: string;
  target_name: string;
  assets_moved: number;
  models_moved?: number;
  models_merged?: number;
  type_links_added?: number;
  message: string;
}

export interface ITAsset {
  id: string;
  asset_number: string;
  legacy_asset_number?: string | null;
  asset_type_id: string;
  asset_type_name?: string | null;
  asset_type_code?: string | null;
  description?: string | null;
  serial_number?: string | null;
  service_tag?: string | null;
  make?: string | null;
  model?: string | null;
  make_id?: string | null;
  model_id?: string | null;
  status: AssetStatus | string;
  purchased_by?: PurchasedBy;
  owner_customer_id?: string | null;
  owner_customer_name?: string | null;
  customer_used_for_id?: string | null;
  customer_used_for_name?: string | null;
  supplier_id?: string | null;
  invoice_number?: string | null;
  condition?: string | null;
  purchase_date?: string | null;
  purchase_cost?: number | string | null;
  warranty_expiry?: string | null;
  /** Derived: none | active | expiring_soon | expired */
  warranty_status?: string | null;
  location?: string | null;
  notes?: string | null;
  assigned_to_user_id?: string | null;
  assigned_to_user_name?: string | null;
  current_assignee_name?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface AssetCustomerReturn {
  id: string;
  asset_id: string;
  asset_number?: string | null;
  asset_type_name?: string | null;
  description?: string | null;
  serial_number?: string | null;
  purchased_by?: string | null;
  owner_customer_id: string;
  owner_customer_name?: string | null;
  return_date: string;
  returned_by_user_id: string;
  returned_by_user_name?: string | null;
  received_by_name?: string | null;
  condition_at_return?: string | null;
  return_reason?: string | null;
  notes?: string | null;
  original_assignee_user_id?: string | null;
  original_assignee_name?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface CustomerAssetReturnReportRow {
  id: string;
  customer?: string | null;
  asset_number?: string | null;
  asset_type?: string | null;
  description?: string | null;
  serial_number?: string | null;
  purchase_owner?: string | null;
  assigned_employee?: string | null;
  return_date: string;
  condition?: string | null;
  returned_by?: string | null;
  received_by?: string | null;
  notes?: string | null;
  return_reason?: string | null;
}

export interface ITAssetCreate {
  asset_type_id: string;
  serial_number?: string | null;
  make?: string | null;
  model?: string | null;
  make_id?: string | null;
  model_id?: string | null;
  supplier_id?: string | null;
  asset_number?: string | null;
  status?: AssetStatus | string;
  purchase_date?: string | null;
  purchase_cost?: number | null;
  warranty_expiry?: string | null;
  location?: string | null;
  notes?: string | null;
}

export interface ITAssetUpdate {
  asset_type_id?: string;
  serial_number?: string | null;
  make?: string | null;
  model?: string | null;
  supplier_id?: string | null;
  status?: AssetStatus | string;
  purchase_date?: string | null;
  purchase_cost?: number | null;
  warranty_expiry?: string | null;
  location?: string | null;
  notes?: string | null;
}

export interface AssetAssignPayload {
  user_id: string;
  assigned_date?: string | null;
  notes?: string | null;
}

export type AssetBulkAction =
  | 'delete'
  | 'assign_user'
  | 'assign_location'
  | 'change_status'
  | 'change_ownership'
  | 'renumber'
  | 'return_to_customer';

export interface AssetBulkActionRequest {
  asset_ids: string[];
  action: AssetBulkAction;
  parameters?: Record<string, unknown>;
  options?: Record<string, unknown>;
}

export interface AssetBulkPreviewResponse {
  action: string;
  selected: number;
  asset_numbers: string[];
  dependencies?: Array<{
    asset_id: string;
    asset_number: string;
    status: string;
    blockers: string[];
    warnings: string[];
    can_delete: boolean;
  }>;
  blocked_count?: number;
  eligible_count?: number;
  already_assigned?: Array<{
    asset_number: string;
    assignee?: string | null;
    has_computer?: boolean;
  }>;
  available?: string[];
  ineligible?: Array<{ asset_number: string; reason: string }>;
  transitions?: Array<{
    asset_number: string;
    from_status: string;
    to_status: string;
    rule: string;
    reason?: string | null;
  }>;
  target_status?: string;
  preview?: Array<{ asset_id: string; current: string; new: string }>;
  batch_duplicates?: string[];
  existing_conflicts?: string[];
  can_apply?: boolean;
  warning?: string;
  eligible?: string[];
}

export interface AssetBulkActionResult {
  action: string;
  selected: number;
  updated: number;
  updated_asset_numbers: string[];
  skipped: number;
  skipped_details: Array<{ asset_number: string; reason: string }>;
  failed: number;
  failed_details: Array<{ asset_number: string; reason: string }>;
  dependencies?: AssetBulkPreviewResponse['dependencies'];
  preview?: AssetBulkPreviewResponse['preview'];
}

export interface AssetBulkIdsResponse {
  ids: string[];
  total: number;
  truncated: boolean;
}

export interface AssetReturnPayload {
  returned_date?: string | null;
  return_condition?: ReturnCondition | null;
  notes?: string | null;
}

export interface AssetTransferPayload {
  to_user_id: string;
  assigned_date?: string | null;
  notes?: string | null;
}

export interface AssetAssignment {
  id: string;
  asset_id: string;
  assigned_to_user_id: string;
  assigned_to_user_name?: string | null;
  assigned_by_user_id: string;
  assigned_by_user_name?: string | null;
  assigned_date: string;
  returned_date?: string | null;
  return_condition?: string | null;
  notes?: string | null;
  created_at?: string;
}

export interface ITComputer {
  id: string;
  asset_id: string;
  computer_name: string;
  asset_number?: string | null;
  asset_type_id?: string | null;
  asset_type_name?: string | null;
  make?: string | null;
  model?: string | null;
  serial_number?: string | null;
  status?: AssetStatus | string | null;
  os?: string | null;
  processor?: string | null;
  ram_gb?: number | null;
  storage_type?: string | null;
  storage_gb?: number | null;
  domain_joined?: boolean | null;
  mac_address?: string | null;
  location?: string | null;
  notes?: string | null;
  assigned_to_user_id?: string | null;
  assigned_to_name?: string | null;
  assigned_to_team?: string | null;
  assigned_to_user_name?: string | null;
  current_assignee_name?: string | null;
  is_open?: boolean;
  assigned_date?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ITPersonListItem {
  user_id: string;
  full_name: string;
  email?: string | null;
  designation?: string | null;
  department?: string | null;
  team?: string | null;
  employment_status: string;
  is_active: boolean;
  has_protrack_login: boolean;
  assigned_computer_id?: string | null;
  assigned_computer_name?: string | null;
  assigned_asset_number?: string | null;
  computer_status?: string | null;
  other_assigned_assets: number;
  it_account_count: number;
}

export interface ITPersonDetail {
  user_id: string;
  full_name: string;
  email?: string | null;
  designation?: string | null;
  department?: string | null;
  team?: string | null;
  employment_status: string;
  is_active: boolean;
  joining_date?: string | null;
  leaving_date?: string | null;
  assigned_computer?: Record<string, unknown> | null;
  assigned_assets: Record<string, unknown>[];
  accounts: Record<string, unknown>[];
  assignment_history: Record<string, unknown>[];
}

export interface ITResetPreview {
  to_delete: Record<string, number>;
  session_cache_files: number;
  total_operational_records: number;
  total_including_session_files: number;
  will_not_delete: Record<string, number>;
  preserved_notes: string[];
  confirm_phrase: string;
  message: string;
}

export interface ITResetResult {
  status: string;
  deleted: Record<string, number>;
  will_not_delete: Record<string, number>;
  message: string;
}

export interface ITComputerCreate {
  asset_type_id: string;
  make?: string | null;
  model?: string | null;
  serial_number?: string | null;
  os?: string | null;
  processor?: string | null;
  ram_gb?: number | null;
  storage_type?: string | null;
  storage_gb?: number | null;
  domain_joined?: boolean | null;
  mac_address?: string | null;
  location?: string | null;
  notes?: string | null;
}

export interface ITComputerUpdate {
  make?: string | null;
  model?: string | null;
  serial_number?: string | null;
  os?: string | null;
  processor?: string | null;
  ram_gb?: number | null;
  storage_type?: string | null;
  storage_gb?: number | null;
  domain_joined?: boolean | null;
  mac_address?: string | null;
  location?: string | null;
  notes?: string | null;
  status?: AssetStatus | string;
}

export interface ITNetwork {
  id: string;
  name: string;
  cidr: string;
  gateway?: string | null;
  dns_primary?: string | null;
  dns_secondary?: string | null;
  vlan_id?: number | null;
  description?: string | null;
  is_active?: boolean;
  total_ips?: number | null;
  available_ips?: number | null;
  allocated_ips?: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface ITNetworkCreate {
  name: string;
  cidr: string;
  gateway?: string | null;
  dns_primary?: string | null;
  dns_secondary?: string | null;
  vlan_id?: number | null;
  description?: string | null;
}

export interface ITNetworkUpdate {
  name?: string;
  cidr?: string;
  gateway?: string | null;
  dns_primary?: string | null;
  dns_secondary?: string | null;
  vlan_id?: number | null;
  description?: string | null;
  is_active?: boolean;
}

export interface ITIpAddress {
  id: string;
  network_id: string;
  address: string;
  status: IpStatus;
  allocation_type?: string | null;
  hostname?: string | null;
  assigned_to_asset_id?: string | null;
  assigned_to_asset_number?: string | null;
  assigned_to_user_id?: string | null;
  assigned_to_user_name?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface IpAllocatePayload {
  ip_address_id?: string | null;
  network_id?: string | null;
  assigned_to_asset_id?: string | null;
  assigned_to_user_id?: string | null;
  hostname?: string | null;
  notes?: string | null;
}

export interface IpReleasePayload {
  notes?: string | null;
}

export interface ITSettings {
  id: string;
  asset_numbering_pattern: string;
  computer_naming_pattern: string;
  default_domain?: string | null;
  default_email_domain?: string | null;
  ip_allocation_strategy: IpAllocationStrategy;
  next_asset_seq?: number;
  next_computer_seq?: number;
  settings_json?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ITSettingsUpdate {
  asset_numbering_pattern?: string;
  computer_naming_pattern?: string;
  default_domain?: string | null;
  default_email_domain?: string | null;
  ip_allocation_strategy?: IpAllocationStrategy;
  settings_json?: string | null;
}

export interface ITProfile {
  user_id: string;
  user_name?: string | null;
  assets: ITAsset[];
  computers?: ITComputer[];
  ips?: ITIpAddress[];
  accounts?: Array<{
    id: string;
    account_type: string;
    username?: string | null;
    display_name?: string | null;
    status: string;
  }>;
}

export interface ITOpenRequest {
  id: string;
  ticket_number?: string;
  title: string;
  status: string;
  status_label?: string;
  priority?: string;
  requester_name?: string | null;
  assignee_name?: string | null;
  created_at?: string;
  category?: string;
}

export interface ITOnboardingTask {
  item_id: string;
  checklist_id: string;
  item_text: string;
  employee_name: string;
  employee_code?: string | null;
  employee_user_id?: string | null;
  joining_date?: string | null;
  help_ticket_id?: string | null;
  owner_user_id?: string | null;
}

export type SoftwareLicenseType =
  | 'named_user'
  | 'floating'
  | 'concurrent'
  | 'device_bound'
  | 'subscription'
  | 'perpetual'
  | 'network'
  | 'other'
  | string;

export interface SoftwareCatalogItem {
  id: string;
  name: string;
  vendor?: string | null;
  version?: string | null;
  edition?: string | null;
  category?: string | null;
  code?: string | null;
  notes?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface SoftwareCatalogCreate {
  name: string;
  vendor?: string | null;
  version?: string | null;
  edition?: string | null;
  category?: string | null;
  code?: string | null;
  notes?: string | null;
  is_active?: boolean;
}

export interface SoftwareCatalogUpdate {
  name?: string;
  vendor?: string | null;
  version?: string | null;
  edition?: string | null;
  category?: string | null;
  code?: string | null;
  notes?: string | null;
  is_active?: boolean;
}

export interface SoftwareLicensePool {
  id: string;
  software_id: string;
  software_name?: string | null;
  purchased_by: string;
  owner_customer_id?: string | null;
  seat_count: number;
  assigned_count: number;
  available_count: number;
  license_type?: SoftwareLicenseType | null;
  cost?: number | string | null;
  currency_code?: string | null;
  expiry_date?: string | null;
  renewal_mode?: string | null;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface SoftwareLicensePoolCreate {
  software_id: string;
  seat_count?: number;
  purchased_by?: string;
  owner_customer_id?: string | null;
  license_type?: SoftwareLicenseType | null;
  cost?: number | null;
  currency_code?: string | null;
  expiry_date?: string | null;
  renewal_mode?: string | null;
  notes?: string | null;
}

export interface SoftwareLicensePoolUpdate {
  seat_count?: number;
  purchased_by?: string;
  owner_customer_id?: string | null;
  license_type?: SoftwareLicenseType | null;
  cost?: number | null;
  currency_code?: string | null;
  expiry_date?: string | null;
  renewal_mode?: string | null;
  notes?: string | null;
}

export interface SoftwareAssignment {
  id: string;
  license_pool_id: string;
  software_id?: string | null;
  software_name?: string | null;
  user_id?: string | null;
  user_name?: string | null;
  computer_id?: string | null;
  computer_name?: string | null;
  asset_id?: string | null;
  assigned_date?: string | null;
  released_date?: string | null;
  notes?: string | null;
  department?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface SoftwareAssignmentCreate {
  license_pool_id: string;
  user_id?: string | null;
  computer_id?: string | null;
  asset_id?: string | null;
  assigned_date?: string | null;
  notes?: string | null;
  department?: string | null;
}

export interface EmployeeSoftwareRequirement {
  id: string;
  user_id: string;
  user_name?: string | null;
  software_id: string;
  software_name?: string | null;
  requirement_level: 'required' | 'optional' | string;
  version?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  reason?: string | null;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface EmployeeSoftwareRequirementCreate {
  user_id: string;
  software_id: string;
  requirement_level?: string;
  version?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  reason?: string | null;
  notes?: string | null;
}

export interface EmployeeSoftwareRequirementUpdate {
  requirement_level?: string;
  version?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  reason?: string | null;
  notes?: string | null;
}

export interface SoftwareExpirySummary {
  active_count: number;
  expiring_30_count: number;
  expired_count: number;
  active: Array<Record<string, unknown>>;
  expiring_30: Array<Record<string, unknown>>;
  expired: Array<Record<string, unknown>>;
}

export interface SoftwareCompliance {
  user_id: string;
  full_name?: string | null;
  requirements: Array<Record<string, unknown>>;
  missing_required_count: number;
  licensed_without_requirement: Array<Record<string, unknown>>;
  is_compliant: boolean;
}
