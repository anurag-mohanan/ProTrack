import type { ExecutionStatus, ProjectHealth, ProjectStage } from './common';
import type { Project } from './Project';
import type { TimesheetEntry } from './TimesheetEntry';

export type TimelineStepStatus = 'completed' | 'current' | 'upcoming' | 'delayed';
export type DecisionCategory =
  | 'design'
  | 'customer'
  | 'manufacturing'
  | 'tooling'
  | 'schedule'
  | 'quality'
  | 'general';
export type ProjectRiskType =
  | 'milestone_delay'
  | 'hours_over_quote'
  | 'overdue'
  | 'missing_approvals'
  | 'designer_overloaded';

export interface CommandCenterHeader {
  tool_number: string;
  part_description: string;
  customer_name: string;
  team_name: string | null;
  designer_name: string | null;
  project_stage: ProjectStage;
  execution_status: ExecutionStatus;
  current_milestone: string | null;
  completion_percent: number;
  health: ProjectHealth;
  priority: 'critical' | 'high' | 'medium' | 'low';
  days_remaining: number;
}

export interface TimelineStep {
  milestone_id: string | null;
  name: string;
  sort_order: number;
  status: TimelineStepStatus;
  due_date: string | null;
  completed_at: string | null;
}

export interface ProjectKpis {
  completion_percent: number;
  quoted_hours: number | null;
  actual_hours: number;
  remaining_hours: number | null;
  variance: number | null;
  variance_percent: number | null;
  budget_consumption_percent: number | null;
  days_remaining: number;
  current_milestone: string | null;
  working_model_id?: string | null;
  working_model_code?: string | null;
  working_model_name?: string | null;
  strategy_key?: string | null;
  show_quoted_variance?: boolean;
  show_over_budget_indicators?: boolean;
  model_metrics?: Record<string, number | string | null>;
}

export interface TeamMemberCapacity {
  user_id: string;
  name: string;
  role: string;
  capacity_hours: number;
  allocated_hours: number;
  available_hours: number;
  availability_status: string;
}

export interface ProjectTeamSummary {
  engineering_manager_name: string | null;
  design_leader_name: string | null;
  designer_name: string | null;
  surfacer_name: string | null;
  team_name: string | null;
  team_colour: string | null;
  members: TeamMemberCapacity[];
}

export interface CustomerProjectSummary {
  customer_id: string;
  customer_name: string;
  customer_code: string | null;
  primary_contact_name: string | null;
  primary_contact_email: string | null;
  active_projects: number;
  completed_projects: number;
  average_hours: number;
}

export interface ProjectDecision {
  id: string;
  project_id: string;
  user_id: string;
  user_name: string | null;
  category: DecisionCategory;
  comment: string;
  milestone_id: string | null;
  milestone_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface EngineeringChange {
  id: string;
  project_id: string;
  ec_number: string;
  title: string;
  status: 'open' | 'closed';
  hours: number;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EngineeringChangeSummary {
  open_count: number;
  closed_count: number;
  total_hours: number;
  items: EngineeringChange[];
}

export interface ProjectRiskItem {
  risk_type: ProjectRiskType;
  severity: string;
  title: string;
  detail: string | null;
}

export interface ProjectFolderPaths {
  project_folder_path: string | null;
  cad_folder_path: string | null;
  released_folder_path: string | null;
  suggested_project_folder: string | null;
  suggested_cad_folder: string | null;
  suggested_released_folder: string | null;
}

export interface ProjectCommandCenter {
  project: Project;
  header: CommandCenterHeader;
  timeline: TimelineStep[];
  kpis: ProjectKpis;
  team: ProjectTeamSummary;
  customer_summary: CustomerProjectSummary;
  decisions: ProjectDecision[];
  recent_timesheets: TimesheetEntry[];
  engineering_changes: EngineeringChangeSummary;
  risks: ProjectRiskItem[];
  folders: ProjectFolderPaths;
  hours: Record<string, number>;
  milestone_summary: Record<string, number>;
}
