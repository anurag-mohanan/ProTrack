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
  qa_acknowledged?: boolean;
  qa_gate_required?: boolean;
  is_required?: boolean;
  project_stage?: string | null;
  template_milestone_id?: string | null;
  depends_on_ids?: string[];
  /** active | merged | superseded | archived. Only active milestones count in progress and reports. */
  lifecycle_state?: 'active' | 'merged' | 'superseded' | 'archived';
  merged_into_id?: string | null;
  lifecycle_reason?: string | null;
  lifecycle_changed_at?: string | null;
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
  qa_acknowledged?: boolean;
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
  in_progress_count?: number;
  not_started_count?: number;
  overall_progress_percent?: number;
  remaining_hours: number;
  quoted_hours: number;
  current_planned_hours: number;
  planned_variance_hours: number;
}

export interface MilestoneReorderItem {
  id: string;
  sort_order: number;
}
