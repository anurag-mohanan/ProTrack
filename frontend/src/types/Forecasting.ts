/** Phase 3 forecasting. Decimal fields arrive as strings. */

export type FcStatus = 'available' | 'preliminary' | 'unavailable';
export type FcValueKind = 'actual' | 'approved_plan' | 'forecast' | 'scenario' | 'commitment';
export type FcGranularity = 'week' | 'month';
type Num = string | number;

export interface FcMetadata {
  forecast_type: string;
  method_version: string;
  generated_at: string;
  as_of: string;
  period_start: string | null;
  period_end: string | null;
  status: FcStatus;
  status_reason: string | null;
  confidence: null;
  confidence_note: string;
  sources: string[];
  assumptions: string[];
  limitations: string[];
}

export interface FcDefinition {
  key: string;
  label: string;
  value_kind: FcValueKind;
  method_version: string;
  description: string;
  deferred: boolean;
  deferred_reason: string | null;
}

export interface FcCatalog {
  definitions: FcDefinition[];
  can_view_engineering: boolean;
  can_view_capacity: boolean;
  can_view_finance: boolean;
}

export interface FcPeriod {
  key: string;
  label: string;
  start_date: string;
  end_date: string;
}

export interface FcProjectEffort {
  project_id: string;
  code: string | null;
  tool_number: string | null;
  execution_status: string;
  quoted_hours: Num | null;
  estimate_source: string;
  approved_original_estimate_hours: Num | null;
  approved_current_estimate_hours: Num | null;
  actual_hours: Num | null;
  actual_status: string;
  actual_unapproved_hours: Num;
  actual_rejected_hours: Num;
  approved_remaining_hours: Num | null;
  forecast_status: FcStatus;
  forecast_reason: string | null;
  forecast_at_completion_hours: Num | null;
  forecast_remaining_hours: Num | null;
  original_commitment_date: string | null;
  original_commitment_source: string;
  current_target_date: string | null;
  target_moved_days: number | null;
  provisional_schedule_date: string | null;
  provisional_schedule_status: string | null;
  completion_forecast_status: FcStatus;
  completion_forecast_reason: string;
  stage_forecast_status: FcStatus;
  stage_forecast_reason: string;
  data_quality_codes: string[];
}

export interface FcEngineering {
  metadata: FcMetadata;
  history: {
    sample_size: number;
    minimum_sample: number;
    factor: Num | null;
    factor_status: FcStatus;
    factor_reason: string | null;
    basis: string;
  };
  backtest: {
    status: 'evaluated' | 'not_possible';
    reason: string | null;
    candidate_count: number;
    evaluated_count: number;
    mean_absolute_error_hours: Num | null;
    mean_absolute_percentage_error: Num | null;
    mean_signed_error_hours: Num | null;
    naive_mean_absolute_error_hours: Num | null;
    naive_mean_absolute_percentage_error: Num | null;
    method: string;
  };
  summary: {
    projects: number;
    available: number;
    preliminary: number;
    unavailable: number;
    approved_remaining_hours: Num;
    forecast_remaining_hours: Num | null;
    forecast_remaining_note: string;
  };
  projects: FcProjectEffort[];
}

export interface FcCapacityCell {
  period_key: string;
  scheduled_hours: Num;
  holiday_hours: Num;
  outside_employment_hours: Num;
  status_unavailable_hours: Num;
  available_hours: Num;
  allocatable_hours: Num;
}

export interface FcCapacity {
  metadata: FcMetadata;
  granularity: FcGranularity;
  periods: FcPeriod[];
  totals: FcCapacityCell[];
  grand_total: FcCapacityCell;
  teams: { team_id: string | null; team_name: string; headcount: number; periods: FcCapacityCell[]; total: FcCapacityCell }[];
  people: {
    user_id: string;
    name: string;
    team_name: string | null;
    hours_source: string;
    availability_status: string;
    max_allocation_percent: number;
    periods: FcCapacityCell[];
    total: FcCapacityCell;
  }[];
  demand: {
    value_kind: FcValueKind;
    approved_remaining_hours: Num;
    projects_with_approved_estimate: number;
    projects_without_approved_estimate: number;
    projects_without_designer: number;
    by_designer: { user_id: string; name: string; approved_remaining_hours: Num; projects: number }[];
    phasing_status: FcStatus;
    phasing_reason: string;
  };
  gap_analysis_status: FcStatus;
  gap_analysis_reason: string;
  skill_demand_status: FcStatus;
  skill_demand_reason: string;
}

export interface FcCurrencyTotals {
  currency: string;
  quotes: number;
  awarded_value: Num;
  invoiced: Num;
  collected: Num;
  outstanding: Num;
  outstanding_scheduled: Num;
  outstanding_overdue: Num;
  outstanding_no_due_date: Num;
  remaining_to_invoice: Num;
  billing_ready: Num;
  billing_dated: Num;
  billing_undated: Num;
  excluded_remaining_to_invoice: Num;
  collections_by_period: Record<string, Num>;
  billing_by_period: Record<string, Num>;
}

export interface FcCollectionItem {
  quote_id: string;
  tool_number: string;
  customer_name: string | null;
  currency: string;
  invoice_line_id: string;
  invoice_number: string | null;
  invoice_date: string | null;
  due_date: string | null;
  outstanding: Num;
  timing: 'scheduled' | 'overdue' | 'no_due_date';
  days_overdue: number | null;
}

export interface FcBillingItem {
  quote_id: string;
  tool_number: string;
  project_code: string | null;
  currency: string;
  kind: 'milestone' | 'unscheduled_remaining';
  milestone_name: string | null;
  trigger_type: string | null;
  amount: Num;
  date_status: 'ready_to_invoice' | 'dated_by_target' | 'undated';
  expected_invoice_date: string | null;
  depends_on_delivery: boolean;
  reason: string;
}

export interface FcFinance {
  metadata: FcMetadata;
  granularity: FcGranularity;
  periods: FcPeriod[];
  totals: FcCurrencyTotals[];
  collections: FcCollectionItem[];
  billing: FcBillingItem[];
  excluded: { quote_id: string; tool_number: string; currency: string; remaining_to_invoice: Num; reason: string }[];
  warnings: string[];
  reconciliation: {
    quotes_considered: number;
    outstanding_matches_ledger: boolean;
    billing_matches_remaining: boolean;
    notes: string[];
  };
}

export interface FcHorizonParams {
  granularity: FcGranularity;
  periods: number;
}
