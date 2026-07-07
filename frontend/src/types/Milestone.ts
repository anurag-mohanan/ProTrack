import type { MilestoneStatus, Timestamped } from './common';

export interface Milestone extends Timestamped {
  project_id: string;
  name: string;
  description: string | null;
  status: MilestoneStatus;
  due_date: string | null;
  completed_at: string | null;
  completed_date: string | null;
  planned_hours: number;
  progress_percent: number;
  assigned_user_id: string | null;
  assigned_user_name: string | null;
  actual_hours: number;
  sort_order: number;
}

export interface MilestoneUpdate {
  status?: MilestoneStatus;
  name?: string;
  description?: string | null;
  due_date?: string | null;
  completed_at?: string | null;
  completed_date?: string | null;
  planned_hours?: number;
  progress_percent?: number;
  assigned_user_id?: string | null;
  sort_order?: number;
}

export interface MilestoneCreate {
  project_id: string;
  name: string;
  description?: string | null;
  status?: MilestoneStatus;
  due_date?: string | null;
  planned_hours?: number;
  progress_percent?: number;
  assigned_user_id?: string | null;
  sort_order?: number;
}

export interface ProjectMilestoneSummary {
  total_planned_hours: number;
  total_actual_hours: number;
  milestone_count: number;
  completed_count: number;
  remaining_hours: number;
  quoted_hours: number;
  current_planned_hours: number;
  planned_variance_hours: number;
}

export interface MilestoneReorderItem {
  id: string;
  sort_order: number;
}
