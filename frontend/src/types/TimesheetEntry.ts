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
  | 'other';

export const CONTRIBUTION_REASON_LABELS: Record<ContributionReason, string> = {
  assisting_designer: 'Assisting Designer',
  peer_review: 'Peer Review',
  design_support: 'Design Support',
  surfacing_support: 'Surfacing Support',
  engineering_change: 'Engineering Change',
  customer_request: 'Customer Request',
  other: 'Other',
};

export interface TimesheetProjectLookup {
  id: string;
  tool_number: string;
  part_description: string;
  customer_name?: string | null;
  designer_name?: string | null;
  surfacer_name?: string | null;
  project_stage: string;
  execution_status: string;
  stream_id?: string | null;
  team_id?: string | null;
  team_name?: string | null;
  design_leader_name?: string | null;
  project_type_name?: string | null;
}

export interface ProjectContributorSummary {
  user_id: string;
  user_name: string;
  role_label: string;
  is_project_owner: boolean;
  total_hours: number;
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
