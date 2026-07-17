import type { Timestamped } from './common';

export interface Team extends Timestamped {
  name: string;
  description: string | null;
  team_lead_id: string | null;
  team_lead_name: string | null;
  colour: string;
  is_active: boolean;
  organization_id: string | null;
  member_count: number;
  /** Customer-paid fixed / retainer headcount (designers & surfacers). */
  billable_member_count?: number;
}

export interface TeamMember extends Timestamped {
  team_id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  role_within_team: string | null;
  joined_at: string;
  is_primary?: boolean;
  is_billable_headcount?: boolean;
  effective_from?: string | null;
}

export interface TeamMemberTransfer {
  target_team_id: string;
  effective_from?: string | null;
  update_reporting_manager?: boolean;
}

export interface TeamMemberAssignPrimary {
  user_id: string;
  effective_from?: string | null;
  update_reporting_manager?: boolean;
}

export interface OrgChartPerson {
  user_id: string;
  member_id: string | null;
  source_team_id: string | null;
  name: string;
  email: string;
  designation: string | null;
  role_name: string | null;
  relationship_type: string;
  is_primary: boolean;
  can_move: boolean;
  is_billable_headcount: boolean;
  manager_id: string | null;
  manager_name: string | null;
  stream_name: string | null;
  company_experience: string | null;
  joining_date: string | null;
  membership_effective_from: string | null;
  org_department_id?: string | null;
  is_department_head?: boolean;
  is_leadership?: boolean;
}

export interface OrgChartTeamColumn {
  team_id: string;
  team_name: string;
  colour: string;
  team_lead_id: string | null;
  team_lead_name: string | null;
  member_count: number;
  org_department_id?: string | null;
  is_delivery_team?: boolean;
  people: OrgChartPerson[];
}

export interface OrgChartDepartment {
  department_id: string;
  code: string;
  name: string;
  description: string | null;
  colour: string;
  sort_order: number;
  head_user_id: string | null;
  head_name: string | null;
  head_title: string | null;
  member_count: number;
  leaders: OrgChartPerson[];
  staff: OrgChartPerson[];
  teams: OrgChartTeamColumn[];
}

export interface OrganizationChart {
  departments?: OrgChartDepartment[];
  teams: OrgChartTeamColumn[];
  unassigned: OrgChartPerson[];
  scope?: 'full' | 'division' | 'team' | 'none' | string;
  note: string;
}

export interface TeamCreate {
  name: string;
  description?: string | null;
  team_lead_id?: string | null;
  colour?: string;
  is_active?: boolean;
  organization_id?: string | null;
}

export interface TeamUpdate {
  name?: string;
  description?: string | null;
  team_lead_id?: string | null;
  colour?: string;
  is_active?: boolean;
  organization_id?: string | null;
}

export interface TeamMemberCreate {
  user_id: string;
  role_within_team?: string | null;
  is_billable_headcount?: boolean;
}

export interface TeamResourcePlanningRow {
  team_id: string;
  team_name: string;
  team_colour: string;
  member_count: number;
  capacity_hours: number;
  allocated_hours: number;
  actual_hours: number;
  remaining_capacity_hours: number;
  utilization_percent: number;
}
