export type AssetStatus =
  | 'available'
  | 'assigned'
  | 'maintenance'
  | 'reserved'
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
  onboarding_it_attention?: number;
  total_computers?: number;
  assigned_computers?: number;
  open_computers?: number;
  available_computers?: number;
  reserved_computers?: number;
  maintenance_computers?: number;
  retired_computers?: number;
  disposed_computers?: number;
  employees_without_computer?: number;
  returned_assets?: number;
  retired_assets?: number;
  disposed_assets?: number;
  awaiting_return_assets?: number;
  lost_assets?: number;
  damaged_assets?: number;
  warranty_window_days?: number;
  warranty_expiring_assets?: number;
  warranty_expired_assets?: number;
  warranty_missing_assets?: number;
  overdue_it_requests?: number;
  unassigned_it_requests?: number;
  computers_without_ip?: number;
  computers_without_mac?: number;
  data_quality_open_issues?: number;
  data_quality_open_records?: number;
  stock_low_items?: number;
  stock_out_items?: number;
  stock_reorder_needed?: number;
  stock_pending_restock?: number;
  stock_incoming_units?: number;
  stock_upcoming_shortages?: number;
  virtual_seat_conflicts?: number;
  virtual_seats_total?: number;
  virtual_seats_incomplete?: number;
  software_catalog_count?: number;
  active_software_count?: number;
  license_pool_count?: number;
  software_assignments_count?: number;
  licenses_expiring_30?: number;
  licenses_expiring_window?: number;
  licenses_expired?: number;
  license_seats_total?: number;
  license_seats_assigned?: number;
  license_seats_available?: number;
  license_authorized_users?: number;
  license_active_usage?: number;
  license_compliance_issues?: number;
  license_metric_unconfigured?: number;
  license_site_pools?: number;
  computers_free_any_shift?: number;
  legacy_assignments_review?: number;
  capacity_by_shift?: ShiftCapacityRow[];
  recent_movements?: ITAssetMovement[];
}

export interface ShiftCapacityRow {
  shift_code: string;
  shift_display: string;
  workstations: number;
  laptops: number;
  monitors: number;
  mouse_3d: number;
  license_rights: number;
}

export interface ITAssetMovement {
  asset_id: string;
  asset_number: string;
  user_id: string;
  user_name: string;
  movement: 'assigned' | 'returned';
  date: string | null;
}

export interface AssetType {
  id: string;
  code: string;
  name: string;
  category: AssetTypeCategory;
  is_active: boolean;
  numbering_prefix?: string | null;
  is_shareable?: boolean | null;
  requires_shift?: boolean | null;
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
  pattern?: string;
  highest_existing_sequence?: number;
  message?: string;
}

export interface NextAssetNumbersPreview {
  asset_type_id: string;
  count: number;
  asset_numbers: string[];
  message?: string;
}

export interface ComputerNameSuggestion {
  computer_name: string;
  prefix?: string | null;
  sequence?: number | null;
  width?: number | null;
  source: string;
  highest_existing_sequence?: number | null;
  sample_names?: string[];
  message: string;
}

export interface ComputerIpSuggestion {
  address?: string | null;
  ip_address_id?: string | null;
  network_id?: string | null;
  network_name?: string | null;
  network_cidr?: string | null;
  allocation_type?: string;
  available: boolean;
  message: string;
}

export interface DuplicateConflict {
  field: string;
  value?: string | null;
  message: string;
  asset_number?: string | null;
  computer_name?: string | null;
  href?: string | null;
}

export interface DuplicateCheckResult {
  ok: boolean;
  conflicts: DuplicateConflict[];
}

export interface AssignmentPreviewCheck {
  code: string;
  ok: boolean;
  message: string;
  team?: string | null;
  location?: string | null;
  shift_id?: string | null;
  derived?: boolean;
}

export interface AssignmentPreview {
  ok: boolean;
  asset_number?: string | null;
  computer_name?: string | null;
  status?: string | null;
  primary_ip?: string | null;
  mac_address?: string | null;
  checks: AssignmentPreviewCheck[];
}

export interface ComputerRecommendation {
  computer_id: string;
  asset_id: string;
  computer_name: string;
  asset_number?: string | null;
  make?: string | null;
  model?: string | null;
  status?: string | null;
  primary_ip?: string | null;
  mac_address?: string | null;
  location?: string | null;
  score: number;
  reasons: string[];
  href?: string | null;
}

export interface ComputerRecommendResult {
  user_id: string;
  user_name?: string | null;
  team?: string | null;
  shift?: string | null;
  recommendations: ComputerRecommendation[];
  message: string;
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
  previous_asset_numbers?: string[];
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
  current_assignee_team?: string | null;
  current_shift_code?: string | null;
  current_shift_name?: string | null;
  current_shift_display?: string | null;
  category?: string | null;
  computer_type?: string | null;
  computer_id?: string | null;
  computer_name?: string | null;
  mac_address?: string | null;
  primary_ip?: string | null;
  ip_address_id?: string | null;
  ip_allocation_type?: string | null;
  network_id?: string | null;
  network_name?: string | null;
  network_cidr?: string | null;
  parent_asset_id?: string | null;
  parent_asset_number?: string | null;
  utilization?: string | null;
  active_assignment_users?: number | null;
  active_assignment_shifts?: number | null;
  configured_shifts?: number | null;
  virtual_seat_id?: string | null;
  virtual_seat_code?: string | null;
  virtual_seat_status?: string | null;
  availability_source?: string | null;
  shift_availability?: {
    shift_id?: string | null;
    shift_code?: string | null;
    shift_name?: string | null;
    shift_display?: string | null;
    status: string;
    reason?: string | null;
    assignees?: { user_id?: string; user_name?: string | null }[];
  }[];
  occupants?: {
    user_id?: string | null;
    user_name?: string | null;
    shift_id?: string | null;
    shift_code?: string | null;
    shift_name?: string | null;
    shift_display?: string | null;
    status?: string | null;
  }[];
  is_shared_seat?: boolean;
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
  computer_type?: string | null;
  serial_number?: string | null;
  make?: string | null;
  model?: string | null;
  make_id?: string | null;
  model_id?: string | null;
  purchased_by?: PurchasedBy;
  owner_customer_id?: string | null;
  customer_used_for_id?: string | null;
  supplier_id?: string | null;
  asset_number?: string | null;
  status?: AssetStatus | string;
  purchase_date?: string | null;
  purchase_cost?: number | null;
  warranty_expiry?: string | null;
  location?: string | null;
  notes?: string | null;
  computer_name?: string | null;
  mac_address?: string | null;
  ip_address_id?: string | null;
  provision_computer?: boolean;
  service_tag?: string | null;
}

export interface ITAssetUpdate {
  asset_type_id?: string;
  computer_type?: string | null;
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
  service_tag?: string | null;
  asset_number?: string | null;
  computer_name?: string | null;
  computer_name_reason?: string | null;
  purchased_by?: PurchasedBy;
  owner_customer_id?: string | null;
}

export interface AssetAssignPayload {
  user_id: string;
  assigned_date?: string | null;
  notes?: string | null;
  /** When set, enables shared-desk dual occupancy for that shift slot. */
  shift_id?: string | null;
  /** Custom daily window (HH:MM); overrides the shift times. Overnight allowed. */
  start_time?: string | null;
  end_time?: string | null;
  planned_end_date?: string | null;
  purpose?: string | null;
  assignment_type?: string | null;
  reservation_id?: string | null;
  force_override?: boolean;
  override_reason?: string | null;
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
  /** Required when multiple open shared-desk assignments exist. */
  shift_id?: string | null;
  assignment_id?: string | null;
}

export interface AssetTransferPayload {
  to_user_id: string;
  assigned_date?: string | null;
  notes?: string | null;
  /** Cascade transfer to child assets linked via parent_asset_id. */
  include_children?: boolean;
}

export interface AssetAssignment {
  id: string;
  asset_id: string;
  assigned_to_user_id: string;
  assigned_to_user_name?: string | null;
  assigned_by_user_id: string;
  assigned_by_user_name?: string | null;
  shift_id?: string | null;
  shift_code?: string | null;
  shift_name?: string | null;
  shift_display?: string | null;
  assigned_date: string;
  planned_end_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  window_label?: string | null;
  needs_review?: boolean;
  purpose?: string | null;
  assignment_type?: string | null;
  override_reason?: string | null;
  returned_date?: string | null;
  released_at?: string | null;
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
  current_shift_code?: string | null;
  current_shift_name?: string | null;
  current_shift_display?: string | null;
  next_shift_code?: string | null;
  next_shift_name?: string | null;
  next_shift_display?: string | null;
  next_change_date?: string | null;
  previous_user_id?: string | null;
  previous_user_name?: string | null;
  other_shift_user_id?: string | null;
  other_shift_user_name?: string | null;
  other_shift_code?: string | null;
  other_shift_name?: string | null;
  other_shift_display?: string | null;
  is_shared_candidate?: boolean;
  data_quality_flags?: string[];
  is_open?: boolean;
  assigned_date?: string | null;
  created_at?: string;
  updated_at?: string;
  primary_ip?: string | null;
  ip_address_id?: string | null;
  ip_allocation_type?: string | null;
  network_id?: string | null;
  network_name?: string | null;
  network_cidr?: string | null;
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
  computer_name?: string | null;
  ip_address_id?: string | null;
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
  computer_name?: string | null;
  computer_name_reason?: string | null;
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
  interface_id?: string | null;
  hostname?: string | null;
  notes?: string | null;
}

export interface IpReleasePayload {
  notes?: string | null;
}

export interface ComputerNetworkInterface {
  id: string;
  computer_id: string;
  name: string;
  role: string;
  mac_address?: string | null;
  is_primary: boolean;
  is_active: boolean;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ComputerNetworkInterfacePayload {
  name: string;
  role?: string;
  mac_address?: string | null;
  is_primary?: boolean;
  is_active?: boolean;
  notes?: string | null;
}

export interface IPAssignmentHistory {
  id: string;
  ip_address_id: string;
  address?: string | null;
  network_cidr?: string | null;
  assigned_to_asset_id?: string | null;
  assigned_to_user_id?: string | null;
  interface_id?: string | null;
  interface_name?: string | null;
  assigned_by_user_id: string;
  hostname?: string | null;
  assigned_date: string;
  released_date?: string | null;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
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

export interface ITProfileComputer {
  computer_id: string;
  computer_name?: string | null;
  asset_id?: string | null;
  asset_number?: string | null;
  asset_status?: string | null;
  assigned_date?: string | null;
  make?: string | null;
  model?: string | null;
  primary_ip?: string | null;
  mac_address?: string | null;
  location?: string | null;
}

export interface ITProfileSoftware {
  assignment_id: string;
  license_pool_id: string;
  software_id: string;
  software_name?: string | null;
  license_type?: string | null;
  assigned_date?: string | null;
}

export interface ITProfileSoftwareStatus {
  software_id: string;
  software_name?: string | null;
  required: boolean;
  installed: boolean;
  licensed: boolean;
  status: string;
}

export interface ITProfileAllocation {
  resource_type: 'asset' | 'license';
  assignment_id: string;
  resource_id: string;
  resource_label: string;
  category: string | null;
  shareable: boolean;
  window_label: string;
  times: string | null;
  shift_name: string | null;
  legacy: boolean;
  allocation_kind: 'scheduled' | 'all_hours' | 'authorization' | 'allocated';
  shared_with: number;
  dates: string;
}

export interface ITProfile {
  user_id: string;
  user_name?: string | null;
  assets: ITAsset[];
  allocations?: ITProfileAllocation[];
  computers?: ITComputer[];
  computer?: ITProfileComputer | null;
  software?: ITProfileSoftware[];
  required_software_count?: number;
  missing_software?: string[];
  software_status?: ITProfileSoftwareStatus[];
  is_compliant?: boolean;
  primary_tool?: string | null;
  primary_tool_source?: string | null;
  shift?: {
    id?: string;
    code?: string | null;
    name?: string | null;
    display?: string | null;
    shift_code?: string | null;
    shift_name?: string | null;
    shift_display?: string | null;
    [key: string]: unknown;
  } | null;
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
  entitlement_code?: string | null;
  purchased_by: string;
  owner_customer_id?: string | null;
  seat_count: number;
  assigned_count: number;
  available_count: number;
  license_type?: SoftwareLicenseType | null;
  commercial_model?: 'perpetual' | 'subscription' | string | null;
  assignment_model?: string | null;
  status?: string | null;
  cost?: number | string | null;
  currency_code?: string | null;
  purchase_date?: string | null;
  expiry_date?: string | null;
  renewal_mode?: string | null;
  renewal_frequency?: string | null;
  renewal_amount?: number | string | null;
  auto_renew?: boolean;
  renewal_notice_days?: number;
  amc_required?: boolean | null;
  amc_percent?: number | string | null;
  amc_amount?: number | string | null;
  amc_amount_overridden?: boolean;
  amc_due_date?: string | null;
  expense_id?: string | null;
  terminated_at?: string | null;
  termination_reason?: string | null;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
  license_metric?: LicenseMetric | null;
  license_metric_label?: string | null;
  license_metric_rule?: string | null;
  rights_allocated?: number | null;
  rights_consumed?: number | null;
  /** null = unlimited (site license). */
  available_rights?: number | null;
  authorized_users?: number | null;
  scheduled_peak?: number | null;
  active_usage?: number | null;
  compliance_status?: LicenseComplianceStatus | null;
  compliance_reason?: string | null;
}

export type LicenseMetric =
  | 'NAMED_USER'
  | 'PER_USER'
  | 'PER_DEVICE'
  | 'CONCURRENT'
  | 'SITE'
  | 'CUSTOM'
  | 'UNSPECIFIED';

export type LicenseComplianceStatus = 'COMPLIANT' | 'FULLY_ALLOCATED' | 'OVER_ALLOCATED' | 'EXPIRED';

export interface SoftwareLicensePoolCreate {
  software_id: string;
  seat_count?: number;
  purchased_by?: string;
  owner_customer_id?: string | null;
  license_type?: SoftwareLicenseType | null;
  commercial_model?: string | null;
  assignment_model?: string | null;
  cost?: number | null;
  currency_code?: string | null;
  purchase_date?: string | null;
  expiry_date?: string | null;
  renewal_mode?: string | null;
  renewal_frequency?: string | null;
  renewal_amount?: number | null;
  auto_renew?: boolean;
  renewal_notice_days?: number;
  amc_required?: boolean | null;
  amc_percent?: number | null;
  amc_amount?: number | null;
  amc_amount_overridden?: boolean;
  expense_id?: string | null;
  notes?: string | null;
}

export interface SoftwareLicensePoolUpdate {
  seat_count?: number;
  purchased_by?: string;
  owner_customer_id?: string | null;
  license_type?: SoftwareLicenseType | null;
  assignment_model?: string | null;
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
  planned_end_date?: string | null;
  released_date?: string | null;
  shift_id?: string | null;
  shift_name?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  window_label?: string | null;
  /** scheduled = consumes a right in its window; authorization = floating, unscheduled; allocated = holds a right. */
  allocation_kind?: 'scheduled' | 'authorization' | 'allocated' | null;
  purpose?: string | null;
  override_reason?: string | null;
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
  planned_end_date?: string | null;
  shift_id?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  purpose?: string | null;
  force_override?: boolean;
  override_reason?: string | null;
  notes?: string | null;
  department?: string | null;
}

export interface SoftwareInstallation {
  id: string;
  computer_id: string;
  computer_name?: string | null;
  software_id: string;
  software_name?: string | null;
  installed_date?: string | null;
  uninstalled_date?: string | null;
  installed_by_user_id?: string | null;
  notes?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
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

export interface ResourcePackageHardwareLine {
  id: string;
  asset_type_id: string;
  asset_type_name?: string | null;
  quantity: number;
  is_required: boolean;
}

export interface ResourcePackageSoftwareLine {
  id: string;
  software_id: string;
  software_name?: string | null;
  requirement_level: string;
  seats: number;
}

export interface ResourcePackage {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  requires_ip: boolean;
  is_active: boolean;
  hardware_lines: ResourcePackageHardwareLine[];
  software_lines: ResourcePackageSoftwareLine[];
  created_at?: string;
  updated_at?: string;
}

export interface ResourcePackageUpsert {
  code: string;
  name: string;
  description?: string | null;
  requires_ip?: boolean;
  is_active?: boolean;
  hardware_lines?: Array<{
    asset_type_id: string;
    quantity: number;
    is_required?: boolean;
  }>;
  software_lines?: Array<{
    software_id: string;
    requirement_level?: string;
    seats?: number;
  }>;
}

export interface ResourcePackagePreview {
  user_id: string;
  user_name?: string;
  package_id: string;
  package_code: string;
  package_name: string;
  requires_ip: boolean;
  on_date: string;
  shift?: { id?: string; name?: string; code?: string } | null;
  hardware: Array<{
    asset_type_id: string;
    asset_type_name: string;
    quantity: number;
    is_required: boolean;
    available_count: number;
    candidates: Array<{
      id: string;
      asset_number: string;
      status: string;
      make?: string | null;
      model?: string | null;
    }>;
  }>;
  software: Array<{
    software_id: string;
    software_name: string;
    requirement_level: string;
    seats: number;
    available_seats: number;
    pools: Array<{
      id: string;
      seat_count: number;
      available_seats: number;
      license_type?: string | null;
      status?: string;
    }>;
  }>;
  ip: {
    required: boolean;
    available_count: number;
    candidates: Array<{ id: string; address: string; network_id: string }>;
  };
  shortages: string[];
  can_assign_without_override: boolean;
}
