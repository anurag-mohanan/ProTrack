export type AllocationResourceType = 'asset' | 'license';

export type AllocationStatus = 'AVAILABLE' | 'ASSIGNED' | 'CONFLICT' | 'RESERVED' | 'UNAVAILABLE' | 'NOT_ALLOWED';

export interface AllocationWindowInput {
  shift_id?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  start_date?: string | null;
  end_date?: string | null;
}

export interface AllocationConflict {
  kind: 'assignment' | 'reservation';
  id: string;
  user_id?: string | null;
  user_name?: string | null;
  window: string;
  times: string;
  dates: string;
  overlap: string;
  legacy: boolean;
}

export interface AllocationCheckResult {
  available: boolean;
  status: AllocationStatus;
  reason_code: string;
  reason: string;
  overridable: boolean;
  can_override?: boolean;
  conflicting_assignments: AllocationConflict[];
  remaining_capacity?: number | null;
  resource_type: AllocationResourceType;
  resource_id: string;
  resource_label?: string | null;
  requested_window?: string;
  requested_dates?: string;
  metric?: string;
  metric_label?: string;
  metric_rule?: string;
  rights_owned?: number;
  rights_allocated?: number;
  authorized_users?: number;
  scheduled_peak?: number;
  active_usage?: number;
}

export interface AllocationCheckRequest extends AllocationWindowInput {
  resource_type: AllocationResourceType;
  resource_id: string;
  user_id?: string | null;
  asset_id?: string | null;
  exclude_assignment_id?: string | null;
}

export interface ScheduleOccupant {
  id: string;
  kind: 'assignment' | 'reservation';
  user_id?: string | null;
  user_name?: string | null;
  window: string;
  times?: string;
  legacy?: boolean;
  assignment_type?: string | null;
  dates: string;
}

export interface ScheduleBlock {
  start: string;
  end: string;
  occupants: ScheduleOccupant[];
  remaining_capacity: number | null;
  available: boolean;
}

export interface SharingPolicy {
  role: string;
  role_label: string;
  shareable: boolean;
  requires_shift: boolean;
  shareable_default: boolean;
  requires_shift_default: boolean;
  configured: boolean;
}

export interface AssetSchedule {
  resource_type: 'asset';
  resource_id: string;
  resource_label: string;
  on_date: string;
  lifecycle_status: string;
  lifecycle_ok: boolean;
  lifecycle_reason: string | null;
  policy: SharingPolicy;
  assignments: ScheduleOccupant[];
  blocks: ScheduleBlock[];
}

export interface LicenseSummary {
  metric: string;
  metric_label: string;
  metric_rule: string;
  shareable: boolean;
  rights_owned: number;
  rights_allocated: number;
  rights_consumed: number;
  available_rights: number | null;
  authorized_users: number;
  scheduled_peak: number | null;
  active_usage: number;
  compliance_status: string;
  compliance_reason: string;
}

export interface LicenseScheduleEntry {
  id: string;
  kind: 'assignment' | 'reservation';
  user_id?: string | null;
  user_name?: string | null;
  asset_id?: string | null;
  window: string;
  times?: string;
  dates: string;
}

export interface LicenseSchedule {
  resource_type: 'license';
  resource_id: string;
  on_date: string;
  summary: LicenseSummary;
  scheduled: LicenseScheduleEntry[];
  authorized_only: LicenseScheduleEntry[];
  blocks: ScheduleBlock[];
}

export interface SetupLineInput {
  resource_type: AllocationResourceType;
  resource_id: string;
  asset_id?: string | null;
}

export interface SetupAssignRequest extends AllocationWindowInput {
  user_id: string;
  lines: SetupLineInput[];
  purpose?: string | null;
  assignment_type?: string | null;
  allow_partial?: boolean;
  dry_run?: boolean;
  force_override?: boolean;
  override_reason?: string | null;
}

export interface SetupLineResult {
  resource_type: AllocationResourceType;
  resource_id: string;
  resource_label?: string;
  result: 'AVAILABLE' | 'ASSIGNED' | 'FAILED' | 'ROLLED_BACK' | AllocationStatus;
  ok: boolean;
  reason: string;
  reason_code?: string;
  assignment_id?: string | null;
  overridable?: boolean;
}

export interface SetupAssignResult {
  committed: boolean;
  dry_run: boolean;
  window: string;
  all_available?: boolean;
  rolled_back?: boolean;
  partial?: boolean;
  lines: SetupLineResult[];
}

export interface ResourceReservation {
  id: string;
  resource_type: AllocationResourceType;
  asset_id: string | null;
  license_pool_id: string | null;
  resource_label: string | null;
  user_id: string | null;
  user_name: string | null;
  reserved_for: string | null;
  provisioning_request_id: string | null;
  shift_id: string | null;
  shift_name: string | null;
  start_time: string | null;
  end_time: string | null;
  window_label: string;
  start_date: string;
  end_date: string | null;
  status: 'ACTIVE' | 'RELEASED' | 'FULFILLED';
  reason: string | null;
  created_by_name: string | null;
  created_at: string | null;
  released_by_name: string | null;
  released_at: string | null;
  release_reason: string | null;
}

export interface ReservationCreate extends AllocationWindowInput {
  resource_type: AllocationResourceType;
  resource_id: string;
  user_id?: string | null;
  reserved_for?: string | null;
  reason?: string | null;
  force_override?: boolean;
  override_reason?: string | null;
}

export interface LicenseUsageSession {
  id: string;
  license_pool_id: string;
  assignment_id: string | null;
  user_id: string;
  user_name: string | null;
  asset_id: string | null;
  checked_out_at: string;
  checked_in_at: string | null;
  source: string;
  checked_out_by_name: string | null;
  checked_in_by_name: string | null;
  notes: string | null;
  is_active: boolean;
}

export interface LegacyAssignment {
  assignment_id: string;
  asset_id: string;
  asset_number: string;
  asset_name: string | null;
  asset_type: string | null;
  role_label: string;
  shareable: boolean;
  requires_shift: boolean;
  user_id: string;
  user_name: string | null;
  assigned_date: string | null;
  assignment_type: string | null;
  status: string;
  reason: string;
}

export interface LegacyLicensePool {
  license_pool_id: string;
  label: string;
  metric: string;
  metric_label: string;
  compliance_status: string;
  rights_owned: number;
  rights_allocated: number;
  issue: string;
}

export interface LegacyReview {
  assignments: LegacyAssignment[];
  license_pools: LegacyLicensePool[];
  counts: { assignments: number; license_pools: number };
}

export interface LegacyResolveRequest {
  mode: 'shift' | 'times' | 'all_hours';
  shift_id?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  force_override?: boolean;
  override_reason?: string | null;
}

export interface SharingPolicyRow extends SharingPolicy {
  asset_type_id: string;
  code: string;
  name: string;
  is_active: boolean;
}
