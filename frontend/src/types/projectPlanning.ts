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

export type MetricStatus = 'available' | 'unavailable' | 'not_applicable';

export interface MetricValue {
  value: Hours | null;
  status: MetricStatus;
  reason: string | null;
}

export interface DataQualityIssue {
  code: string;
  severity: 'info' | 'warning';
  message: string;
}

export interface MetricDefinition {
  key: string;
  label: string;
  definition: string;
}

export interface StageHoursRow {
  key: string;
  label: string;
  has_approved_estimate: boolean;
  original_estimate_hours: Hours | null;
  current_estimate_hours: Hours | null;
  actual_hours: Hours | null;
  percent_of_project_actual: Hours | null;
  variance_hours: Hours | null;
  variance: MetricValue;
  utilization_percent: MetricValue;
  remaining_hours: MetricValue;
  data_quality: 'complete' | 'limited' | 'unavailable';
  data_quality_notes: string[];
}

export type DeliveryStatus =
  | 'early'
  | 'on_time'
  | 'late'
  | 'overdue'
  | 'not_due'
  | 'no_target'
  | 'completion_date_missing'
  | 'not_applicable';

export type DeliveryReference = 'original_baseline' | 'baseline_unverified' | 'current_due_date' | 'none';

export interface ProjectDelivery {
  status: DeliveryStatus;
  reference_source: DeliveryReference;
  reference_label: string;
  reference_date: string | null;
  original_baseline_completion_date: string | null;
  current_baseline_completion_date: string | null;
  current_due_date: string | null;
  current_target_date: string | null;
  actual_completion_date: string | null;
  schedule_variance_days: number | null;
  current_target_variance_days: number | null;
  days_overdue: number | null;
  target_moved_days: number | null;
  baseline_revision_count: number;
  original_due_date_preserved: boolean;
}

export interface MilestoneDelivery {
  milestone_id: string;
  name: string;
  stage: string | null;
  stage_label: string | null;
  milestone_status: string;
  is_required: boolean;
  original_baseline_finish_date: string | null;
  current_baseline_finish_date: string | null;
  current_due_date: string | null;
  current_target_date: string | null;
  actual_completion_date: string | null;
  reference_date: string | null;
  reference_source: DeliveryReference;
  status: DeliveryStatus;
  schedule_variance_days: number | null;
  days_overdue: number | null;
}

export interface DeliveryMetrics {
  sign_convention: string;
  project: ProjectDelivery;
  milestones: MilestoneDelivery[];
  milestone_status_counts: Record<string, number>;
}

export interface ProjectEngineeringMetrics {
  project_id: string;
  code: string | null;
  tool_number: string | null;
  part_description: string | null;
  execution_status: string;
  data_quality_status: 'available' | 'available_with_limitations' | 'unavailable';
  estimate: {
    quoted_hours: Hours | null;
    original_estimate_hours: Hours | null;
    current_estimate_hours: Hours | null;
    estimate_source: 'stage_estimates' | 'milestone_hours' | 'quoted_hours' | 'none';
    estimate_source_label: string;
    revision_count: number;
    last_revised_at: string | null;
  };
  actual: {
    status: 'recorded' | 'none_recorded' | 'missing';
    total_hours: Hours | null;
    entry_count: number;
    before_completion_hours: Hours;
    post_completion_hours: Hours;
    approved_hours: Hours;
    submitted_hours: Hours;
    draft_hours: Hours;
    rejected_hours: Hours;
  };
  variance_hours: MetricValue;
  utilization_percent: MetricValue;
  remaining_hours: MetricValue;
  original_variance_hours: MetricValue;
  stage_attribution: {
    status: 'complete' | 'partial' | 'unavailable' | 'no_hours';
    coverage_percent: Hours | null;
    total_hours: Hours | null;
    attributed_hours: Hours;
    unattributed_hours: Hours;
    other_stage_hours: Hours;
    no_stage_hours: Hours;
    no_milestone_hours: Hours;
    invalid_milestone_hours: Hours;
    source: string;
    rows: StageHoursRow[];
  };
  milestones: {
    total: number;
    completed: number;
    open: number;
    skipped: number;
    open_required: number;
    open_without_target_date: number;
    open_overdue: number;
    completed_with_completion_date: number;
    with_baseline_finish_date: number;
    with_original_planned_hours: number;
    current_target_date: string | null;
    baseline_completion_date: string | null;
    original_baseline_completion_date: string | null;
    baseline_revision_count: number;
    actual_completion_date: string | null;
  };
  delivery: DeliveryMetrics;
  quote_linkage: {
    status: 'linked' | 'unlinked' | 'ambiguous';
    active_quote_count: number;
    details_visible: boolean;
    quote_reference: string | null;
    quote_version: number | null;
    quote_revision: string | null;
    quote_hours: Hours | null;
  };
  issues: DataQualityIssue[];
  definitions: MetricDefinition[];
  calculated_at: string;
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
