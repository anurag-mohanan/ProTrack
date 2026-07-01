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
}

export interface TeamMember extends Timestamped {
  team_id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  role_within_team: string | null;
  joined_at: string;
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
