import type { Timestamped } from './common';

export type WorkCategory = 'productive' | 'non_productive';

export type NonProductiveCodeCategory = 'non_productive' | 'leave';

export interface TimesheetEntry extends Timestamped {
  timesheet_id: string;
  work_category: WorkCategory;
  project_id: string | null;
  customer_id: string | null;
  task_type_id: string | null;
  milestone_id: string | null;
  non_productive_code_id: string | null;
  entry_date: string;
  hours: number;
  is_billable: boolean;
  leave_count?: number | null;
  description: string | null;
  project_tool_number?: string | null;
  project_code?: string | null;
  /** Owning team of the project (for cross-team support detection). */
  project_team_id?: string | null;
  project_team_name?: string | null;
  customer_name?: string | null;
  task_type_name?: string | null;
  milestone_name?: string | null;
  non_productive_code?: string | null;
  non_productive_description?: string | null;
  non_productive_category?: NonProductiveCodeCategory | null;
  user_id?: string | null;
  user_name?: string | null;
  contribution_reason?: ContributionReason | null;
}

export type ContributionReason =
  | 'assisting_designer'
  | 'peer_review'
  | 'design_support'
  | 'surfacing_support'
  | 'engineering_change'
  | 'customer_request'
  | 'training_mentoring'
  | 'rework_quality'
  | 'other';

export const CONTRIBUTION_REASON_LABELS: Record<ContributionReason, string> = {
  assisting_designer: 'Assisting Designer',
  peer_review: 'Peer Review',
  design_support: 'Design Support',
  surfacing_support: 'Surfacing Support',
  engineering_change: 'Engineering Change',
  customer_request: 'Customer Request',
  training_mentoring: 'Training / Mentoring',
  rework_quality: 'Rework / quality issue (non-billable)',
  other: 'Other',
};

/** Project hours logged as rework from quality issues — always non-billable. */
export const REWORK_QUALITY_REASON: ContributionReason = 'rework_quality';

export function isReworkQualityReason(
  reason: string | null | undefined,
): reason is typeof REWORK_QUALITY_REASON {
  return reason === REWORK_QUALITY_REASON;
}

export interface TimesheetProjectLookup {
  id: string;
  tool_number: string;
  part_description: string;
  customer_name?: string | null;
  designer_id?: string | null;
  surfacer_id?: string | null;
  designer_name?: string | null;
  surfacer_name?: string | null;
  project_stage: string;
  execution_status: string;
  stream_id?: string | null;
  team_id?: string | null;
  team_name?: string | null;
  design_leader_name?: string | null;
  project_type_name?: string | null;
  working_model_name?: string | null;
  working_model_code?: string | null;
  health?: string | null;
  quoted_hours?: number | null;
  actual_hours?: number | null;
  remaining_hours?: number | null;
  is_assigned_to_user?: boolean;
}

export interface ContributorReasonHours {
  reason_key?: ContributionReason | null;
  reason_label: string;
  hours: number;
}

export interface ProjectContributorSummary {
  user_id: string;
  user_name: string;
  role_label: string;
  is_project_owner: boolean;
  total_hours: number;
  hours_percent?: number;
  primary_contribution_label?: string | null;
  contribution_reasons?: ContributorReasonHours[];
}

export interface TimesheetProjectMilestoneDue {
  id: string;
  name: string;
  due_date?: string | null;
  status: string;
}

export interface TimesheetProjectContext {
  project_id: string;
  tool_number: string;
  part_description: string;
  customer_name?: string | null;
  project_stage: string;
  execution_status: string;
  health: string;
  working_model_name?: string | null;
  quoted_hours: number;
  actual_hours: number;
  remaining_hours: number;
  milestones_due: TimesheetProjectMilestoneDue[];
  contributor_count: number;
  is_assigned_to_user: boolean;
}

export interface TimesheetEntryCreate {
  timesheet_id: string;
  work_category?: WorkCategory;
  project_id?: string | null;
  customer_id?: string | null;
  task_type_id?: string | null;
  milestone_id?: string | null;
  non_productive_code_id?: string | null;
  entry_date: string;
  hours: number;
  is_billable?: boolean;
  description?: string | null;
  contribution_reason?: ContributionReason | null;
}

export interface NonProductiveCode extends Timestamped {
  code: string;
  description: string | null;
  category?: NonProductiveCodeCategory;
  is_active: boolean;
  is_archived: boolean;
  sort_order: number;
}

export interface NonProductiveCodeCreate {
  code: string;
  description?: string | null;
  category?: NonProductiveCodeCategory;
  is_active?: boolean;
  sort_order?: number;
}

export interface NonProductiveCodeUpdate {
  code?: string;
  description?: string | null;
  category?: NonProductiveCodeCategory;
  is_active?: boolean;
  is_archived?: boolean;
  sort_order?: number;
}

export interface MembershipDateWindow {
  start: string;
  end: string;
}

export interface TimesheetOverviewTeam {
  team_id: string | null;
  team_name: string;
  user_ids: string[];
  /** Inclusive intervals when each user belonged to this team in the overview month. */
  membership_windows?: Record<string, MembershipDateWindow[]>;
  /** management = full unsplit hours; delivery = membership-dated; unassigned = no team */
  section_kind?: 'management' | 'delivery' | 'unassigned' | string;
}

export interface TimesheetOverviewUser {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  team_id?: string | null;
  team_name?: string | null;
  team_ids: string[];
  working_hours_per_day: number;
  requires_timesheet?: boolean;
}

export interface TimesheetOverviewContext {
  teams: TimesheetOverviewTeam[];
  users: TimesheetOverviewUser[];
  scope_all_teams: boolean;
  month_start?: string | null;
  month_end?: string | null;
}
