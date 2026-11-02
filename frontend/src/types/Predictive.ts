export type PredictionStatus = 'predicted' | 'insufficient_data';

export type PredictionTypeKey =
  | 'project_delivery'
  | 'project_final_hours'
  | 'milestone_delay'
  | 'resource_demand'
  | 'finance_billing'
  | 'finance_collections';

export interface PredictionFactor {
  name: string;
  value: string | number | boolean | null;
  role: 'calculation' | 'context';
  detail: string | null;
}

/** One stored prediction. Numbers arrive as strings so nothing is rounded on the way. */
export interface Prediction {
  id: string;
  prediction_type: PredictionTypeKey;
  type_label: string;
  model_version: string;
  is_shadow: boolean;
  is_latest: boolean;
  subject_type: string;
  subject_key: string;
  subject_label: string;
  project_id: string | null;
  milestone_id: string | null;
  team_id: string | null;
  currency: string | null;
  as_of: string;
  horizon_start: string | null;
  horizon_end: string | null;
  status: PredictionStatus;
  reason: string | null;
  unit: string;
  predicted_value: string | null;
  predicted_date: string | null;
  lower_value: string | null;
  upper_value: string | null;
  lower_date: string | null;
  upper_date: string | null;
  range_basis: string | null;
  probability: string | null;
  observed_frequency: string | null;
  baseline_label: string | null;
  baseline_value: string | null;
  baseline_date: string | null;
  variance_value: string | null;
  sample_size: number | null;
  comparison_group: string | null;
  factors: PredictionFactor[];
  data_used: Record<string, unknown>;
  warnings: string[];
  outcome_status: string | null;
  actual_value: string | null;
  actual_date: string | null;
  abs_error: string | null;
  pct_error: string | null;
  outcome_note: string | null;
}

export interface PredictionFreshness {
  last_run_as_of: string | null;
  stale: boolean;
  disabled_types: string[];
  message: string;
}

export interface PredictionRunRead {
  id: string;
  status: string;
  trigger: string;
  as_of: string;
  started_at: string | null;
  finished_at: string | null;
  counts: Record<string, Record<string, number>> | null;
  error: string | null;
}

export interface PredictionCapabilities {
  run: boolean;
  manage_models: boolean;
  scenarios: boolean;
  capacity: boolean;
  finance: boolean;
  patterns: boolean;
}

export interface PredictionTypeInfo {
  key: PredictionTypeKey;
  label: string;
  module: string;
  unit: string;
  description: string;
  enabled: boolean;
  active_version: string | null;
  visible: boolean;
}

export interface PredictionCoverage {
  predicted: number;
  insufficient: number;
  top_reasons: Array<{ reason: string; count: number }>;
}

export interface PredictionOverview {
  freshness: PredictionFreshness;
  latest_run: PredictionRunRead | null;
  can: PredictionCapabilities;
  types: PredictionTypeInfo[];
  likely_late: Prediction[];
  likely_overrun: Prediction[];
  late_milestones: Prediction[];
  completion_trend: Array<{ month: string; projects: number }>;
  coverage: Record<'project_delivery' | 'project_final_hours' | 'milestone_delay', PredictionCoverage>;
  bottlenecks: {
    people: Prediction[];
    teams: Prediction[];
    skills: Prediction[];
    coverage: PredictionCoverage;
  } | null;
  finance: { billing: Prediction[]; collections: Prediction[] } | null;
}

export interface PredictionList {
  prediction_type: PredictionTypeKey;
  freshness: PredictionFreshness;
  predictions: Prediction[];
}

export interface ProjectRecordedFigures {
  committed_date: string | null;
  committed_source: string | null;
  current_target: string | null;
  start_date: string | null;
  start_source: string | null;
  quoted_hours: string | null;
  original_estimate: string | null;
  current_estimate: string | null;
  estimate_approved: boolean;
  estimate_source: string | null;
  actual_hours: string | null;
  actual_status: string | null;
  unapproved_hours: string | null;
  open_milestones: number;
  overdue_milestones: number;
}

export interface ProjectPredictionDetail {
  project: {
    id: string;
    code: string | null;
    tool_number: string | null;
    part_description: string | null;
    execution_status: string | null;
  };
  recorded: ProjectRecordedFigures | null;
  delivery: Prediction | null;
  final_hours: Prediction | null;
  milestones: Prediction[];
  history: Record<'project_delivery' | 'project_final_hours', Prediction[]>;
  freshness: PredictionFreshness;
  can_scenarios: boolean;
}

export interface AccuracyMetrics {
  evaluated: number;
  reportable: boolean;
  message?: string;
  mean_absolute_error?: number | null;
  median_absolute_error?: number | null;
  mean_bias?: number | null;
  mean_absolute_percentage_error?: number | null;
  percentage_error_n?: number;
  naive_baseline?: { n: number; model_mae: number | null; baseline_mae: number | null; better_than_baseline: boolean };
  range_coverage?: { n: number; inside_share: number; expected_share: number };
}

export interface AccuracyVersion {
  version: string;
  status: string;
  description: string | null;
  registered_at: string | null;
  activated_at: string | null;
  activation_note: string | null;
  accuracy: AccuracyMetrics;
}

export interface AccuracyTypeReport {
  prediction_type: PredictionTypeKey;
  label: string;
  unit: string;
  module: string;
  enabled: boolean;
  disabled_reason: string | null;
  active_version: string | null;
  pending: number;
  not_evaluable: number;
  overall: AccuracyMetrics;
  by_horizon: Array<AccuracyMetrics & { horizon: string }>;
  calibration: Array<{ band: string; n: number; event_rate?: number }>;
  degradation: {
    status: 'insufficient' | 'stable' | 'degraded';
    recent_n: number;
    earlier_n: number;
    recent_mae?: number;
    earlier_mae?: number;
    message: string;
  };
  versions: AccuracyVersion[];
  examples: Array<{ subject: string; predicted: string; actual: string; abs_error: string; as_of: string }>;
}

export interface AccuracyReport {
  minimum_evaluated: number;
  types: AccuracyTypeReport[];
  can_manage: boolean;
}

export interface PatternRow {
  metric: string;
  metric_label: string;
  dimension: string;
  group_label: string;
  stratum: string | null;
  n: number;
  comparison_n: number;
  comparison_group: string;
  group_median: number;
  comparison_median: number;
  difference: number;
  p_value: number | null;
  significant: boolean;
  finding: string | null;
  period_start: string | null;
  period_end: string | null;
}

export interface PatternReport {
  patterns: PatternRow[];
  no_reliable_difference: PatternRow[];
  too_small: Array<{ metric: string; dimension: string; group_label: string; stratum?: string | null; n: number; comparison_n: number }>;
  metrics?: Array<{ key: string; label: string; rule: string; projects: number }>;
  limitations: string[];
}

export interface ScenarioAssumptions {
  scope_change_percent?: string | number;
  extra_delay_days?: number;
  target_shift_days?: number;
  milestone_delays?: Record<string, number>;
  designer_id?: string | null;
  added_hours_per_week?: string | number;
  start_date?: string | null;
}

export interface ScenarioOutcome {
  status: PredictionStatus;
  reason: string | null;
  unit: string;
  label: string;
  predicted_value: string | null;
  predicted_date: string | null;
  lower_value: string | null;
  upper_value: string | null;
  lower_date: string | null;
  upper_date: string | null;
  baseline_label: string | null;
  baseline_value: string | null;
  baseline_date: string | null;
  variance_value: string | null;
  sample_size: number | null;
  comparison_group: string | null;
  factors: PredictionFactor[];
  warnings: string[];
}

export interface ScenarioSide {
  final_hours: ScenarioOutcome | null;
  delivery: ScenarioOutcome | null;
  milestones: ScenarioOutcome[];
  designer_load: {
    designer_id: string;
    designer_name: string;
    weeks: number;
    demand_hours: string;
    capacity_hours: string;
    utilisation_percent: string | null;
    projects_without_estimate: number;
  } | null;
}

export interface ScenarioResult {
  label: string;
  as_of: string;
  project: { id: string; label: string };
  assumptions: ScenarioAssumptions;
  model_versions: Record<string, string>;
  baseline: ScenarioSide;
  scenario: ScenarioSide;
  comparison: Array<{ measure: string; baseline: string; scenario: string; difference: string | null }>;
  warnings: string[];
}

export interface SavedScenario {
  id: string;
  name: string;
  project_id: string;
  as_of: string;
  created_by: string | null;
  created_at: string | null;
  updated_by: string | null;
  updated_at: string | null;
  assumptions: ScenarioAssumptions;
  result: ScenarioResult;
  label: string;
}

export interface ScenarioList {
  label: string;
  scenarios: SavedScenario[];
  can_edit: boolean;
}
