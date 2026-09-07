import type { TeamResourcePlanningRow } from './Team';

export type ResourcePlanningGranularity = 'day' | 'week' | 'month';

export type ResourceStatusColor = 'green' | 'blue' | 'orange' | 'red' | 'grey';

export interface ResourceAllocationBlock {
  project_id: string;
  tool_number: string;
  customer_name: string;
  milestone_name: string | null;
  hours: number;
  status_color: ResourceStatusColor;
  complexity?: string | null;
}

export interface ResourcePlanningPeriod {
  key: string;
  label: string;
  start_date: string;
  end_date: string;
}

export interface ResourcePlanningCell {
  period_key: string;
  capacity_hours: number;
  allocated_hours: number;
  remaining_hours: number;
  status_color: ResourceStatusColor;
  blocks: ResourceAllocationBlock[];
}

export interface ResourcePlanningDesignerRow {
  user_id: string;
  designer_name: string;
  team_name: string | null;
  availability_status: string;
  skill_level?: string | null;
  capacity_hours: number;
  allocated_hours: number;
  remaining_hours: number;
  cells: ResourcePlanningCell[];
}

export interface UnassignedProjectBlock {
  project_id: string;
  tool_number: string;
  customer_name: string;
  quoted_hours: number;
  remaining_hours: number;
  due_date: string | null;
  milestone_name: string | null;
  complexity?: string | null;
}

export interface ResourcePlanningGrid {
  granularity: ResourcePlanningGranularity;
  start_date: string;
  end_date: string;
  periods: ResourcePlanningPeriod[];
  designers: ResourcePlanningDesignerRow[];
  unassigned_projects: UnassignedProjectBlock[];
  team_summary: TeamResourcePlanningRow[];
}

/** IT readiness — read-only projections over IT Operations (Wave 4). */

export type ITGapSeverity = 'error' | 'warning' | 'success' | 'info';

export interface ITGapAlert {
  severity: ITGapSeverity;
  code: string;
  message: string;
  count: number;
}

export interface ITGapUser {
  user_id: string;
  full_name: string;
  email: string | null;
}

export interface ITGapUserMissingLicenses extends ITGapUser {
  missing: { software_id: string; software_name: string | null }[];
}

export interface ITLicenseDemandRow {
  software_id: string;
  software_name: string | null;
  required_headcount: number;
  unmet_headcount: number;
  seat_count: number;
  assigned_seats: number;
  available_seats: number;
  is_floating: boolean;
  peak_estimate: number;
  seat_shortfall: number;
  has_pool: boolean;
}

export interface ITLicensePoolRow {
  pool_id: string;
  software_id: string;
  software_name: string | null;
  license_type: string | null;
  is_floating: boolean;
  seat_count: number;
  assigned_seats: number;
  available_seats: number;
  expiry_date: string | null;
  is_expired: boolean;
  expires_soon: boolean;
}

export interface ResourceITGaps {
  on_date: string;
  team_id: string | null;
  headcount: number;
  users_without_computer: ITGapUser[];
  users_missing_licenses: ITGapUserMissingLicenses[];
  license_demand: ITLicenseDemandRow[];
  oversubscribed_software: ITLicenseDemandRow[];
  software_without_pool: ITLicenseDemandRow[];
  expiring_pools: ITLicensePoolRow[];
  expired_pools: ITLicensePoolRow[];
  spare_computers: number;
  total_computers: number;
  alerts: ITGapAlert[];
}

export interface ResourceITMatrixRow {
  user_id: string;
  full_name: string;
  email: string | null;
  team_name: string | null;
  has_computer: boolean;
  computer_name: string | null;
  asset_number: string | null;
  required_software_count: number;
  licensed_software_count: number;
  missing_software: string[];
  is_compliant: boolean;
  is_ready: boolean;
}

export interface ResourceITMatrix {
  from_date: string;
  to_date: string;
  team_id: string | null;
  headcount: number;
  ready_count: number;
  not_ready_count: number;
  rows: ResourceITMatrixRow[];
}
