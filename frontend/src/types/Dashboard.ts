import type { ExecutionStatus, ProjectHealth, ProjectStage } from './common';
import type { Project } from './Project';
import type { TimesheetEntry } from './TimesheetEntry';

export interface DashboardSummary {
  total_projects: number;
  active_projects: number;
  being_worked_on_projects: number;
  on_hold_projects: number;
  cancelled_projects: number;
  completed_projects: number;
  archived_projects: number;
  projects_due_this_week: number;
  overdue_projects: number;
  completed_this_month: number;
  not_started_projects: number;
  in_progress_projects: number;
  billable_hours: number;
  non_billable_hours: number;
  np_hours: number;
  productive_percent: number;
  total_quoted_hours: number;
  total_actual_hours: number;
  total_quoted_hours_active: number;
  total_actual_hours_productive: number;
  total_remaining_hours: number;
  hours_variance: number;
  completed_milestones: number;
  total_milestones: number;
  overall_progress_percent: number;
  green_projects: number;
  yellow_projects: number;
  red_projects: number;
  attention_projects: ProjectAttentionRow[];
  my_tasks: DashboardMyTasks;
  recent_activity: import('./Workflow').Activity[];
  activity_feed: DashboardActivityItem[];
  customer_workload: DashboardCustomerWorkloadRow[];
  designer_availability_summary: DashboardDesignerAvailabilitySummary;
  designer_availability: DashboardDesignerAvailabilityRow[];
  team_summary: DashboardTeamSummaryRow[];
  projects_by_stage: DashboardProjectStageRow[];
  hours_logged_today: number;
  open_engineering_changes: number;
  np_hours_this_month: number;
  leave_days_this_month: number;
  np_hours_panel: DashboardNpPanel;
  leave_panel: DashboardLeavePanel;
  operational_metrics: DashboardOperationalMetrics;
  staff_metrics?: StaffDashboardMetrics | null;
}

export interface DashboardOperationalMetrics {
  pending_timesheet_approvals: number;
  pending_project_approvals: number;
  pending_import_jobs: number;
}

export interface StaffDashboardMetrics {
  my_projects: number;
  current_tool_number?: string | null;
  current_part_description?: string | null;
  assigned_milestones: number;
  hours_logged_this_week: number;
  pending_timesheet_submissions: number;
  upcoming_due_dates: number;
  task_label: string;
}

export interface DashboardNpCodeRow {
  code: string;
  description: string;
  hours_this_month: number;
}

export interface DashboardNpPanel {
  total_np_hours_this_month: number;
  codes: DashboardNpCodeRow[];
}

export interface DashboardLeavePanel {
  leave_days_this_month: number;
}

export interface DashboardOverview {
  kpis: DashboardKpis;
  projects_requiring_attention: ProjectAttentionRow[];
  my_tasks: DashboardMyTasks;
  recent_activity: import('./Workflow').Activity[];
  placeholders: DashboardFuturePlaceholders;
}

export interface DashboardKpis {
  being_worked_on_projects: number;
  on_hold_projects: number;
  cancelled_projects: number;
  completed_this_month: number;
  projects_due_this_week: number;
  overdue_projects: number;
  archived_projects: number;
  total_quoted_hours_active: number;
  total_actual_hours_productive: number;
  np_hours_this_month: number;
  in_progress_projects: number;
}

export interface ProjectAttentionRow {
  project_id: string;
  tool_number: string;
  customer_name: string;
  current_milestone: string | null;
  designer_name: string | null;
  due_date: string;
  health: ProjectHealth;
  execution_status: ExecutionStatus;
  attention_reason: 'overdue' | 'blocked' | 'due_soon' | 'on_hold';
}

export interface DashboardTaskItem {
  id: string;
  title: string;
  task_type: string;
  subtitle?: string | null;
  due_date?: string | null;
  project_code?: string | null;
  project_id?: string | null;
  href?: string | null;
  priority?: 'high' | 'medium' | 'low' | string | null;
}

export interface DashboardCustomerWorkloadRow {
  customer_id: string;
  customer_name: string;
  active_tools: number;
  quoted_hours: number;
  actual_hours: number;
  designers_assigned: number;
}

export interface DashboardDesignerAvailabilitySummary {
  total_designers: number;
  allocated: number;
  available: number;
  on_leave: number;
}

export type DesignerAvailabilityStatus = 'available' | 'working' | 'on_hold' | 'leave';

export interface DashboardDesignerAvailabilityRow {
  user_id: string;
  designer_name: string;
  status: DesignerAvailabilityStatus;
  current_tool_number?: string | null;
  current_customer_name?: string | null;
  current_stage?: import('./common').ProjectStage | null;
  current_milestone?: string | null;
}

export interface DashboardTeamSummaryRow {
  team_id: string;
  team_name: string;
  team_colour?: string | null;
  project_count: number;
  designer_count: number;
  quoted_hours: number;
  actual_hours: number;
  available_capacity_hours: number;
}

export interface DashboardProjectStageRow {
  project_stage: ProjectStage;
  project_count: number;
}

export type DashboardActivityCategory =
  | 'project'
  | 'milestone'
  | 'timesheet'
  | 'user'
  | 'import';

export interface DashboardActivityItem {
  id: string;
  category: DashboardActivityCategory;
  title: string;
  detail?: string | null;
  actor_name?: string | null;
  occurred_at: string;
  href?: string | null;
}

export interface DashboardMyTasks {
  pending_approvals: DashboardTaskItem[];
  upcoming_milestones: DashboardTaskItem[];
  pending_reviews: DashboardTaskItem[];
}

export interface DashboardFuturePlaceholders {
  notifications_enabled: boolean;
  ai_recommendations_enabled: boolean;
  todays_priorities_enabled: boolean;
}

export interface DesignerWorkload {
  user_id: string;
  designer_name: string;
  role: string;
  active_projects: number;
  hours_this_week: number;
  quoted_hours_assigned: number;
  actual_hours_logged: number;
}

export interface MilestoneSummary {
  completed: number;
  remaining: number;
  progress_percent: number;
}

export interface ProjectHoursSummary {
  quoted: number;
  actual: number;
  remaining: number;
  variance: number;
}

export interface ProjectDashboard {
  project: Project;
  milestone_summary: MilestoneSummary;
  hours: ProjectHoursSummary;
  health: ProjectHealth;
  recent_timesheet_entries: TimesheetEntry[];
}
