import type { ProjectHealth } from './common';
import type { Project } from './Project';
import type { TimesheetEntry } from './TimesheetEntry';

export interface DashboardSummary {
  total_projects: number;
  active_projects: number;
  not_started_projects: number;
  in_progress_projects: number;
  completed_projects: number;
  archived_projects: number;
  on_hold_projects: number;
  projects_due_this_week: number;
  overdue_projects: number;
  completed_this_month: number;
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
}

export interface DashboardOverview {
  kpis: DashboardKpis;
  projects_requiring_attention: ProjectAttentionRow[];
  my_tasks: DashboardMyTasks;
  recent_activity: import('./Workflow').Activity[];
  placeholders: DashboardFuturePlaceholders;
}

export interface DashboardKpis {
  in_progress_projects: number;
  on_hold_projects: number;
  completed_this_month: number;
  projects_due_this_week: number;
  overdue_projects: number;
  archived_projects: number;
  total_quoted_hours_active: number;
  total_actual_hours_productive: number;
}

export interface ProjectAttentionRow {
  project_id: string;
  tool_number: string;
  customer_name: string;
  current_milestone: string | null;
  designer_name: string | null;
  due_date: string;
  health: ProjectHealth;
  status: import('./common').ProjectStatus;
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
}

export interface DashboardMyTasks {
  pending_approvals: DashboardTaskItem[];
  upcoming_milestones: DashboardTaskItem[];
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
