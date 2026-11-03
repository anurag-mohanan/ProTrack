export type MetricKind = 'actual' | 'approved_plan' | 'forecast' | 'target' | 'manual' | 'baseline';
export type MetricUnit = 'currency' | 'percentage' | 'count' | 'hours' | 'days' | 'ratio';
export type MetricStatus = 'available' | 'limited' | 'unavailable' | 'restricted' | 'not_started';

export interface Metric {
  key: string;
  label: string;
  value: number | null;
  unit: MetricUnit;
  kind: MetricKind;
  status: MetricStatus;
  note: string | null;
  sample: number | null;
  source: string | null;
}

export interface ManagementCan {
  finance: boolean;
  workforce: boolean;
  capacity: boolean;
  hr: boolean;
  org_wide: boolean;
  manage_strategy: boolean;
  approve_strategy: boolean;
  export: boolean;
  reviews: boolean;
}

export interface PeriodInfo {
  start: string;
  end: string;
  label: string;
  fy_start_year: number | null;
  fy_start_month: number;
}

export interface FilterOptions {
  financial_years: { start_year: number; label: string; is_current: boolean }[];
  fy_start_month: number;
  customers: { id: string; name: string }[];
  classifications: { value: string; label: string }[];
  project_managers: { id: string; name: string }[];
  project_manager_basis: string;
  teams: { id: string; name: string }[];
  business_units: string[];
  business_unit_supported: boolean;
  can: ManagementCan;
}

export interface CockpitFilterValues {
  fy_start_year?: number;
  start_date?: string;
  end_date?: string;
  customer_id?: string;
  classification?: string;
  manager_id?: string;
  team_id?: string;
  business_unit?: string;
}

export interface KpiDefinition {
  key: string;
  label: string;
  unit: MetricUnit;
  kind: MetricKind;
  definition: string;
  source: string;
  finance: boolean;
}

export interface Hidden {
  visible: false;
  reason: string;
}

export interface CustomerRow {
  customer_id: string;
  customer: string;
  projects: number;
  active_projects: number;
  completed_in_period: number;
  on_time_rate: number | null;
  delivery_evaluable: number;
  hour_variance_percent: number | null;
  comparable_projects: number;
  invoiced?: number;
  awarded?: number;
  collected?: number;
  outstanding?: number;
  previous_period_invoiced?: number;
  revenue_trend_percent?: number | null;
}

export interface BusinessSection {
  visible: true;
  currency: string;
  as_of: string;
  kpis: Metric[];
  monthly: { month: string; invoiced: number; collected: number; mom_growth_percent: number | null; elapsed: boolean }[];
  customers: {
    customer_id: string;
    customer: string;
    invoiced: number;
    share_percent: number | null;
    collected: number;
    awarded: number;
    outstanding: number;
    segment: 'new' | 'repeat' | null;
  }[];
  new_vs_repeat: {
    status: string;
    new_customers: number;
    repeat_customers: number;
    new_revenue: number;
    repeat_revenue: number;
    note: string;
  };
  notes: string[];
}

export interface HoursBlock {
  quoted_hours: Metric;
  approved_estimate_hours: Metric;
  actual_hours: Metric;
  comparable_projects: number;
  projects_over_estimate: number;
  projects_not_comparable: number;
}

export interface EffortRow {
  key: string;
  label: string;
  hours: number | null;
  projects: number;
  share_percent: number | null;
}

export interface OperationsSection {
  kpis: Metric[];
  completed: { population: string; projects: number; hours: HoursBlock; delivery: Record<string, number | null> };
  active: { population: string; projects: number; hours: HoursBlock; overdue: number; at_risk: number; forecast_risk: number };
  effort_by_stage: EffortRow[];
  throughput: { month: string; completed: number }[];
  warnings: { message: string }[];
  notes: string[];
}

export interface WorkforceSection {
  visible: true;
  kpis: Metric[];
  capacity: Record<string, unknown>;
  training: { completion_rate: Metric; assignments: Record<string, number>; open_development_plans: number };
  skills:
    | Hidden
    | {
        visible: true;
        skills_tracked: number;
        skills_with_verified_coverage: number;
        single_specialist_skills: number;
        critical_gaps: { severity: string; skill_name: string; explanation: string }[];
        distribution: { category: string; skills: number; verified_records: number; skills_without_verified: number }[];
      };
  bottlenecks: Hidden | { visible: true; people_short: number; teams_short: number; skills_short: number; note: string };
  limitations: string[];
}

export interface Cockpit {
  generated_at: string;
  as_of: string;
  filters: { period: PeriodInfo; labels: Record<string, string | null> };
  can: ManagementCan;
  business: BusinessSection | Hidden;
  operations: OperationsSection;
  workforce: WorkforceSection | Hidden;
  customers: { rows: CustomerRow[]; total: number; finance_visible: boolean; notes: string[] };
  definitions: KpiDefinition[];
  principle: string;
}

export interface CustomerTable {
  rows: CustomerRow[];
  finance_visible: boolean;
  previous_period: PeriodInfo;
  notes: string[];
}

export interface DeliveryStats {
  completed_projects: number;
  delivery_evaluable: number;
  on_time: number;
  late: number;
  on_time_rate: number | null;
  average_variance_days: number | null;
  comparable_projects: number;
  projects_over_estimate: number;
  approved_estimate_hours: number | null;
  actual_hours: number | null;
  hour_variance_percent: number | null;
}

export interface CustomerSignal {
  code: string;
  label: string;
  evidence: string;
  sample: number;
  observed: boolean;
}

export interface CustomerProfile {
  customer: { id: string; name: string; code: string | null; country: string | null; city: string | null };
  contacts: { name: string; job_title: string | null; email: string | null; phone: string | null; is_primary: boolean }[];
  projects: {
    total: number;
    by_status: Record<string, number>;
    by_classification: Record<string, number>;
    active: { project_id: string; code: string | null; tool_number: string | null; status: string; current_target_date: string | null; delivery_status: string }[];
    completed_in_period: { project_id: string; code: string | null; tool_number: string | null; actual_completion_date: string | null; delivery_variance_days: number | null }[];
  };
  delivery: { period: DeliveryStats; history: DeliveryStats };
  finance: { currency: string; kpis: Metric[]; all_time: Record<string, number | null> } | null;
  finance_visible: boolean;
  trend: (DeliveryStats & { fy_start_year: number; label: string; invoiced: number | null })[];
  signals: CustomerSignal[];
  not_assessable: { code: string; reason: string }[];
  forecasts: {
    items: { prediction_type: string; subject: string; predicted_value: number | null; predicted_date: string | null; unit: string | null; as_of: string }[];
    note: string;
  };
  notes: string[];
}

export interface EfficiencyGroup extends DeliveryStats {
  key: string;
  label: string;
  classification_mix: Record<string, number>;
}

export interface Efficiency {
  compare_by: string;
  dimension_label: string;
  dimensions: { value: string; label: string }[];
  kpis: Metric[];
  comparison: EfficiencyGroup[];
  effort: Record<string, EffortRow[]>;
  warnings: { message: string }[];
  fairness_note: string;
  notes: string[];
}

export type ObjectiveStatus = 'not_started' | 'on_track' | 'at_risk' | 'delayed' | 'completed' | 'cancelled';

export interface ManagementEvent {
  id: string;
  event_type: string;
  summary: string;
  body: string | null;
  reason: string | null;
  actor: string | null;
  approved_by: string | null;
  created_at: string | null;
}

export interface Objective {
  id: string;
  title: string;
  description: string | null;
  fy_start_year: number;
  period_type: string;
  period: PeriodInfo;
  category: string;
  unit: MetricUnit;
  direction: 'increase' | 'decrease';
  measurement: 'automatic' | 'manual';
  metric_key: string | null;
  metric_label: string | null;
  owner_id: string | null;
  owner: string | null;
  start_date: string;
  target_date: string;
  status: ObjectiveStatus;
  target_state: 'approved' | 'proposed';
  target_approved_by: string | null;
  restricted: boolean;
  restricted_reason: string | null;
  can_edit: boolean;
  can_change_target: boolean;
  can_record_measurement: boolean;
  target: { value: number | null; kind: 'target'; state: string } | null;
  baseline: { value: number | null; kind: 'baseline'; note: string | null } | null;
  current: { value: number | null; kind: string; status: string; note?: string | null } | null;
  progress_percent: number | null;
  pace: { expected_percent: number; time_elapsed_percent: number; basis: string; suggested_status: string | null; note: string };
  events?: ManagementEvent[];
  measurements?: { id: string; period_start: string; period_end: string; value: number; note: string | null; evidence: string | null; recorded_at: string }[];
}

export interface KpiOption {
  key: string;
  label: string;
  unit: MetricUnit;
  direction: 'increase' | 'decrease';
  scope: string;
  params: string[];
  required_params: string[];
  point_in_time: boolean;
  definition: string | null;
  source: string | null;
}

export interface Initiative {
  id: string;
  name: string;
  description: string | null;
  objective_id: string | null;
  objective: string | null;
  owner_id: string | null;
  owner: string | null;
  start_date: string | null;
  target_date: string | null;
  status: string;
  priority: string;
  progress_percent: number;
  progress_kind: 'reported';
  overdue: boolean;
  milestones: { title: string; due_date: string | null; done: boolean }[];
  milestones_done: number;
  projects: { id: string; code: string | null; status: string | null }[];
  projects_hidden: number;
  can_edit: boolean;
}

export type ActionStatus = 'open' | 'in_progress' | 'blocked' | 'completed' | 'cancelled';

export interface ManagementAction {
  id: string;
  title: string;
  description: string | null;
  owner_id: string | null;
  owner: string | null;
  priority: string;
  due_date: string | null;
  status: ActionStatus;
  status_reason?: string | null;
  completion_evidence?: string | null;
  overdue: boolean;
  review: { id: string; title: string } | null;
  objective: { id: string; title: string } | null;
  project: { id: string; code: string | null } | null;
  can_edit?: boolean;
  created_at: string | null;
}

export interface ActionList {
  actions: ManagementAction[];
  summary: { open: number; overdue: number; blocked: number; due_next_14_days: number };
  can: ManagementCan;
}

export interface ReviewSummary {
  id: string;
  review_type: string;
  title: string;
  status: 'draft' | 'final';
  period: { start: string; end: string };
  generated_at: string | null;
  generated_by: string | null;
  finalised_at: string | null;
  finalised_by: string | null;
  executive_summary: string | null;
  can_edit: boolean;
  can_finalise: boolean;
  sections: string[];
}

export interface ReviewSection {
  visible?: boolean;
  reason?: string;
  kpis?: Metric[];
  notes?: string[];
  limitations?: string[];
}

export interface ReviewDetail extends ReviewSummary {
  snapshot: {
    executive_summary: { generated_highlights: string[]; note: string };
    financial: ReviewSection;
    delivery: ReviewSection;
    efficiency: ReviewSection;
    workforce: ReviewSection;
    customer: { rows: CustomerRow[]; total: number; finance_columns: boolean; notes: string[] };
    objectives: { id: string; title: string; status: string; owner: string | null; restricted?: boolean; progress_percent: number | null }[];
    risks: { top: { project: string; title: string; severity: string }[] };
    decisions_required: { type: string; text: string }[];
    action_items: { open: number; overdue: number; blocked: number };
    forecasts: { stored_predictions: Record<string, number>; projects_forecast_risk: number | null; note: string };
  };
  events: ManagementEvent[];
  decisions: ManagementEvent[];
  actions: ManagementAction[];
}

export interface ReviewComparison {
  other: ReviewSummary | null;
  rows: { key: string; label: string; unit: MetricUnit; section: string; current: number | null; previous: number | null; change: number | null }[];
  note: string;
}

export type ManagementReport =
  | 'fy-performance'
  | 'customer-contribution'
  | 'delivery'
  | 'efficiency'
  | 'utilisation'
  | 'objectives'
  | 'review'
  | 'actions';
