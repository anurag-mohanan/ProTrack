import type { Project } from './Project';
import type { TimesheetEntry } from './TimesheetEntry';

export interface DashboardSummary {
  total_projects: number;
  not_started_projects: number;
  in_progress_projects: number;
  completed_projects: number;
  on_hold_projects: number;
  total_quoted_hours: number;
  total_actual_hours: number;
  hours_variance: number;
  completed_milestones: number;
  total_milestones: number;
  overall_progress_percent: number;
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
  variance: number;
}

export interface ProjectDashboard {
  project: Project;
  milestone_summary: MilestoneSummary;
  hours: ProjectHoursSummary;
  recent_timesheet_entries: TimesheetEntry[];
}
