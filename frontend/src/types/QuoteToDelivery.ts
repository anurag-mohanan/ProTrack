import type { KpiDefinition, PerformanceDataWarning, PerformancePeriodType } from './EngineeringPerformance';

/** Decimal fields arrive as JSON strings; counts and day values are numbers. */
type Hours = number | string;

export type QtdPopulationKey = 'completed' | 'active';
export type QtdDataQuality = 'available' | 'available_with_limitations' | 'unavailable';

export type QtdSegment =
  | 'over_estimate'
  | 'under_estimate'
  | 'on_estimate'
  | 'not_comparable'
  | 'metrics_incomplete'
  | 'stage_eligible'
  | 'stage_over'
  | 'stage_missing_attribution'
  | 'stage_no_estimate'
  | 'delivered_on_or_before'
  | 'delivered_after'
  | 'delivery_not_evaluable'
  | 'overdue_milestones'
  | 'past_target'
  | 'no_target';

export interface QuoteToDeliveryParams {
  period_type: PerformancePeriodType;
  anchor?: string;
  start_date?: string;
  end_date?: string;
  population: QtdPopulationKey;
  customer_id?: string;
  team_id?: string;
  design_leader_id?: string;
  designer_id?: string;
  project_type_id?: string;
  project_classification?: string;
  status?: string;
  include_archived?: boolean;
  search?: string;
  segment?: QtdSegment;
  stage?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export interface QtdSummary {
  eligible_projects: number;
  quoted_hours_total: Hours;
  projects_with_quoted_hours: number;
  current_estimate_total: Hours;
  projects_with_current_estimate: number;
  estimate_source_counts: Record<string, number>;
  actual_hours_total: Hours;
  projects_with_actual_hours: number;
  projects_actual_missing: number;
  comparable_projects: number;
  comparable_estimate_hours: Hours;
  comparable_actual_hours: Hours;
  variance_hours: Hours | null;
  utilization_percent: Hours | null;
  projects_over_estimate: number;
  projects_under_estimate: number;
  projects_on_estimate: number;
  projects_not_comparable: number;
  projects_metrics_unavailable: number;
  projects_metrics_limited: number;
}

export interface QtdProjectRow {
  project_id: string;
  code: string | null;
  tool_number: string | null;
  part_description: string | null;
  customer_name: string | null;
  classification: string | null;
  classification_label: string | null;
  project_type_name: string | null;
  execution_status: string;
  design_leader_name: string | null;
  designer_name: string | null;
  quoted_hours: Hours | null;
  current_estimate_hours: Hours | null;
  estimate_source: string;
  estimate_source_label: string;
  actual_hours: Hours | null;
  actual_status: 'recorded' | 'none_recorded' | 'missing';
  variance_hours: Hours | null;
  utilization_percent: Hours | null;
  comparable: boolean;
  original_baseline_completion_date: string | null;
  current_baseline_completion_date: string | null;
  current_target_date: string | null;
  delivery_reference_source: 'original_baseline' | 'baseline_unverified' | 'current_due_date' | 'none';
  actual_completion_date: string | null;
  delivery_variance_days: number | null;
  delivery_status: string;
  days_overdue: number | null;
  open_overdue_milestones: number;
  stage_attribution_status: string;
  data_quality_status: QtdDataQuality;
  data_quality_issues: string[];
  data_quality_warnings: string[];
}

export interface QtdProjectPage {
  items: QtdProjectRow[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  search: string | null;
  segment: QtdSegment | null;
  stage: string | null;
  sort: string;
}

export interface QtdStageRow {
  key: string;
  label: string;
  projects_in_plan: number;
  eligible_projects: number;
  estimate_hours: Hours | null;
  actual_hours: Hours | null;
  variance_hours: Hours | null;
  utilization_percent: Hours | null;
  projects_over_estimate: number;
  projects_missing_attribution: number;
  projects_without_estimate: number;
  explanation: string | null;
}

export interface QtdHistoricalDelivery {
  population_rule: string;
  completed_projects: number;
  eligible_projects: number;
  on_or_before_baseline: number;
  after_baseline: number;
  average_variance_days: number | null;
  median_variance_days: number | null;
  excluded_baseline_unverified: number;
  excluded_due_date_only: number;
  excluded_no_reference: number;
  completed_without_completion_date: number;
}

export interface QtdOperationalDelivery {
  population_rule: string;
  as_of: string;
  active_projects: number;
  projects_with_overdue_milestones: number;
  overdue_milestones: number;
  projects_past_current_target: number;
  projects_without_current_target: number;
  projects_without_original_baseline: number;
}

export interface QuoteToDeliveryReport {
  population: { key: QtdPopulationKey; label: string; date_basis: string; as_of: string };
  period: {
    period_type: PerformancePeriodType;
    label: string;
    start_date: string;
    end_date: string;
    financial_year_start_month: number;
    applies_to: string;
  };
  filters: Record<string, string | null>;
  summary: QtdSummary;
  projects: QtdProjectPage;
  stages: { rows: QtdStageRow[]; eligibility_rule: string; source: string };
  delivery: {
    sign_convention: string;
    historical: QtdHistoricalDelivery;
    operational: QtdOperationalDelivery;
  };
  warnings: PerformanceDataWarning[];
  definitions: KpiDefinition[];
  empty_message: string | null;
  generated_at: string;
}
