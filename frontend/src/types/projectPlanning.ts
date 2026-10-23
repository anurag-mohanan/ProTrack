import type { MilestoneStatus } from './common';

type Hours = number | string;

export interface StagePlanMilestone {
  id: string;
  name: string;
  sort_order: number;
  status: MilestoneStatus;
  is_required: boolean;
  original_planned_hours: Hours | null;
  planned_hours: Hours;
  actual_hours: Hours;
  forecast_remaining_hours: Hours;
  estimate_basis: string | null;
  baseline_start_date: string | null;
  baseline_finish_date: string | null;
  forecast_start_date: string | null;
  forecast_finish_date: string | null;
  actual_start_date: string | null;
  actual_finish_date: string | null;
  due_date: string | null;
  override_start_date: string | null;
  override_finish_date: string | null;
  override_reason: string | null;
  depends_on: string[];
  overdue: boolean;
  forecast_late: boolean;
}

export interface StagePlanStage {
  key: string;
  label: string;
  configured: boolean;
  original_hours: Hours | null;
  current_hours: Hours | null;
  milestone_planned_hours: Hours;
  actual_hours: Hours;
  forecast_remaining_hours: Hours;
  eac_hours: Hours;
  variance_hours: Hours;
  variance_percent: Hours | null;
  allocation_mismatch: boolean;
  milestones: StagePlanMilestone[];
}

export interface EstimateRevision {
  id: string;
  stage: string;
  stage_label: string;
  previous_hours: Hours;
  new_hours: Hours;
  reason: string;
  revised_by_id: string | null;
  revised_by_name: string | null;
  revised_at: string;
}

export interface BaselineRevision {
  id: string;
  revision_number: number;
  previous_start_date: string | null;
  previous_completion_date: string | null;
  new_start_date: string | null;
  new_completion_date: string | null;
  reason: string;
  revised_by_id: string | null;
  revised_by_name: string | null;
  revised_at: string;
}

export interface ProjectStagePlan {
  project_id: string;
  start_date: string | null;
  baseline_start_date: string | null;
  baseline_completion_date: string | null;
  baseline_version: number;
  forecast_completion_date: string | null;
  forecast_status: string | null;
  forecast_note: string | null;
  forecast_calculated_at: string | null;
  actual_start_date: string | null;
  actual_completion_date: string | null;
  due_date: string | null;
  stage_estimates_configured: boolean;
  original_total_hours: Hours | null;
  current_total_hours: Hours | null;
  actual_total_hours: Hours;
  forecast_remaining_hours: Hours;
  eac_hours: Hours;
  variance_hours: Hours;
  variance_percent: Hours | null;
  stages: StagePlanStage[];
  estimate_revisions: EstimateRevision[];
  baseline_revisions: BaselineRevision[];
  effort_hours_per_day: Hours;
  effort_source: string;
}
