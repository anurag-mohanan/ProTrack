export type PerformancePeriodType = 'weekly' | 'monthly' | 'quarterly' | 'yearly' | 'custom';
export type PerformancePlanBasis = 'current' | 'original';

export interface EngineeringPerformanceParams {
  period_type: PerformancePeriodType;
  anchor?: string;
  start_date?: string;
  end_date?: string;
  plan_basis: PerformancePlanBasis;
  customer_id?: string;
  end_customer_id?: string;
  team_id?: string;
  design_leader_id?: string;
  designer_id?: string;
  surfacer_id?: string;
  project_type_id?: string;
  template_id?: string;
  include_archived?: boolean;
}

export interface PerformancePeriod {
  period_type: PerformancePeriodType;
  label: string;
  start_date: string;
  end_date: string;
  financial_year_start_month: number;
}

export interface KpiDefinition {
  key: string;
  label: string;
  definition: string;
}

export interface PerformanceSummary {
  projects_completed: number;
  plan_basis: PerformancePlanBasis;
  planned_hours: number;
  projects_without_plan: number;
  actual_hours: number;
  eac_hours: number;
  variance_hours: number;
  variance_percent: number | null;
  on_time_projects: number;
  late_projects: number;
  projects_without_reference_date: number;
  on_time_rate: number | null;
  average_days_late: number | null;
  milestones_total: number;
  milestones_completed: number;
  milestones_on_time: number;
  milestone_on_time_rate: number | null;
}

export interface StagePerformanceRow {
  stage: string;
  label: string;
  projects: number;
  original_hours: number;
  current_hours: number;
  actual_hours: number;
  variance_hours: number;
  variance_percent: number | null;
}

export interface StagePerformance {
  projects_with_stage_plan: number;
  projects_without_stage_plan: number;
  rows: StagePerformanceRow[];
  unstaged_actual_hours: number;
}

export interface BreakdownRow {
  key: string;
  label: string;
  projects: number;
  planned_hours: number;
  actual_hours: number;
  variance_hours: number;
  variance_percent: number | null;
  on_time_projects: number;
  on_time_rate: number | null;
}

export interface Breakdown {
  dimension: string;
  label: string;
  rows: BreakdownRow[];
}

export interface ProjectPerformanceRow {
  project_id: string;
  code: string | null;
  tool_number: string | null;
  part_description: string | null;
  customer_name: string | null;
  end_customer_name: string | null;
  team_name: string | null;
  design_leader_name: string | null;
  designer_name: string | null;
  surfacer_name: string | null;
  project_type_name: string | null;
  template_name: string | null;
  start_date: string | null;
  actual_start_date: string | null;
  actual_completion_date: string;
  reference_completion_date: string | null;
  reference_source: 'baseline' | 'legacy_due_date' | 'none';
  on_time: boolean | null;
  days_late: number | null;
  original_planned_hours: number | null;
  current_planned_hours: number | null;
  planned_hours: number | null;
  plan_source: string;
  actual_hours: number;
  variance_hours: number | null;
  variance_percent: number | null;
  stage_planned: boolean;
  milestones_total: number;
  milestones_completed: number;
  milestones_on_time: number;
}

export interface PerformanceDataWarning {
  code: string;
  message: string;
  project_codes: string[];
}

export interface EngineeringPerformanceReport {
  period: PerformancePeriod;
  filters: Record<string, string | null>;
  summary: PerformanceSummary;
  stage_performance: StagePerformance;
  breakdowns: Breakdown[];
  projects: ProjectPerformanceRow[];
  warnings: PerformanceDataWarning[];
  definitions: KpiDefinition[];
  empty_message: string | null;
}

export interface TemplateLookup {
  id: string;
  template_family_id: string;
  name: string;
  version: number;
  is_active: boolean;
}

export interface DataQualityItem {
  id: string;
  kind: 'project' | 'customer';
  label: string | null;
  description: string | null;
  detail: string | null;
}

export interface DataQualityCheck {
  code: string;
  label: string;
  severity: 'high' | 'medium' | 'low';
  description: string;
  count: number;
  items: DataQualityItem[];
}

export interface EngineeringDataQuality {
  generated_at: string;
  projects_checked: number;
  total_issues: number;
  checks: DataQualityCheck[];
}