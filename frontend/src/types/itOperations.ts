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
  assigned_to_user_name?: string | null;
  current_assignee_name?: string | null;
  created_at?: string;
  updated_at?: string;
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
