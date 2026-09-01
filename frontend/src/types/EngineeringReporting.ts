export interface ReportPeriod {
  period_type: string;
  label: string;
  start_date: string;
  end_date: string;
  working_days: number;
}

export interface ReportCatalogEntry {
  id: string;
  title: string;
  description: string;
  category: string;
  supported_periods: string[];
  export_formats: string[];
  drill_down_routes: Record<string, string>;
}

export interface ReportCatalog {
  reports: ReportCatalogEntry[];
}

export interface ExecutiveKpiCard {
  label: string;
  value: string;
  accent?: string | null;
}

export interface ExecutiveSummary {
  period: ReportPeriod;
  company_name: string;
  kpis: ExecutiveKpiCard[];
  total_engineering_hours: number;
  productive_hours: number;
  non_productive_hours: number;
  billable_percent: number;
  utilization_percent: number;
  leave_days: number;
  team_size: number;
}

export interface DesignerProductivityRow {
  user_id: string;
  designer_name: string;
  team_id?: string | null;
  team_name?: string | null;
  productive_hours: number;
  non_productive_hours: number;
  leave_days: number;
  total_hours: number;
  billable_percent: number;
  utilization_percent?: number | null;
  project_count: number;
  customer_count: number;
  applicable_start_date?: string | null;
  applicable_end_date?: string | null;
  applicable_working_days?: number;
  available_hours?: number;
}

export interface ToolHoursRow {
  project_id?: string | null;
  tool_number: string;
  customer_name: string;
  part_description?: string | null;
  design_leader_name?: string | null;
  designer_name?: string | null;
  surfacer_name?: string | null;
  quoted_hours: number;
  actual_hours: number;
  variance_hours: number;
  completion_percent: number;
  original_hours?: number;
  additional_work_hours?: number;
  rework_hours?: number;
  customer_change_hours?: number;
  internal_correction_hours?: number;
  post_completion_hours?: number;
  current_stage?: string | null;
  execution_status?: string | null;
}

export interface CustomerHoursRow {
  customer_id?: string | null;
  customer_name: string;
  project_count: number;
  productive_hours: number;
  np_hours: number;
  total_hours: number;
  designer_count: number;
  avg_hours_per_project: number;
  original_hours?: number;
  additional_work_hours?: number;
  rework_hours?: number;
  customer_change_hours?: number;
  internal_correction_hours?: number;
}

export interface DesignerTeamTimesheetPayload {
  report_id: string;
  title: string;
  company_name: string;
  period: ReportPeriod;
  generated_at: string;
  designers: DesignerProductivityRow[];
  projects: ToolHoursRow[];
  total_designer_hours: number;
  total_project_actual_hours: number;
  team_count: number;
  designer_count: number;
  project_count: number;
  /** False for single-customer or retainer/subscription team reports. */
  include_customer_columns?: boolean;
  /** Hours where the designer's home team differs from the project's team. */
  cross_team_hours?: CrossTeamHoursRow[];
  cross_team_hours_outbound?: number;
  cross_team_hours_inbound?: number;
  selected_sections?: string[];
}

export interface TimesheetReportSectionOption {
  id: string;
  label: string;
  description: string;
}

export interface CrossTeamHoursRow {
  direction: 'outbound' | 'inbound' | 'cross' | string;
  user_id: string;
  designer_name: string;
  home_team_id?: string | null;
  home_team_name?: string | null;
  project_id: string;
  tool_number: string;
  project_team_id?: string | null;
  project_team_name?: string | null;
  customer_name?: string | null;
  hours: number;
  contribution_reason?: string | null;
}

export interface DesignerToolBreakdownRow {
  designer_name: string;
  tool_number: string;
  customer_name: string;
  design_hours: number;
  surfacing_hours: number;
  review_hours: number;
  bom_hours: number;
  meeting_hours: number;
  np_hours: number;
  other_hours: number;
  total_hours: number;
}

export interface TeamSummaryRow {
  team_name: string;
  designer_count: number;
  project_count: number;
  productive_hours: number;
  np_hours: number;
  leave_days: number;
  total_hours: number;
  utilization_percent: number;
}

export interface FunctionHoursRow {
  function_group: string;
  hours: number;
  percent: number;
}

export interface NpAnalysisRow {
  code: string;
  description: string;
  hours: number;
  percent: number;
}

export interface LeaveAnalysisRow {
  designer_name: string;
  leave_days: number;
  leave_hours: number;
}

export interface QuotedVsActualRow {
  tool_number: string;
  customer_name: string;
  quoted_hours: number;
  actual_hours: number;
  variance_hours: number;
  variance_percent: number;
  completion_percent: number;
  health?: string | null;
  late_milestones: number;
  original_hours?: number;
  additional_work_hours?: number;
  rework_hours?: number;
  customer_change_hours?: number;
  internal_correction_hours?: number;
  post_completion_hours?: number;
}

export interface ProjectPerformanceRow {
  tool_number: string;
  customer_name: string;
  designer_name?: string | null;
  surfacer_name?: string | null;
  project_stage?: string | null;
  quoted_hours: number;
  actual_hours: number;
  milestone_completion_percent: number;
  health?: string | null;
  predicted_finish?: string | null;
}

export interface DetailedTimesheetRow {
  entry_date: string;
  designer_name: string;
  team_name?: string | null;
  customer_name?: string | null;
  tool_number?: string | null;
  task_name?: string | null;
  hours: number;
  is_billable: boolean;
  category: string;
  notes?: string | null;
  post_completion_type?: string | null;
}

export interface EngineeringReportPayload {
  report_id: string;
  period: ReportPeriod;
  company_name: string;
  executive: ExecutiveSummary;
  designer_productivity: DesignerProductivityRow[];
  designer_tool_breakdown: DesignerToolBreakdownRow[];
  tool_hours: ToolHoursRow[];
  customer_summary: CustomerHoursRow[];
  team_summary: TeamSummaryRow[];
  function_hours: FunctionHoursRow[];
  np_analysis: NpAnalysisRow[];
  leave_analysis: LeaveAnalysisRow[];
  quoted_vs_actual: QuotedVsActualRow[];
  project_performance: ProjectPerformanceRow[];
  detailed_entries: DetailedTimesheetRow[];
  charts: { title: string; labels: string[]; values: number[] }[];
  ai_insights: string[];
}

export interface ReportScheduleEntry {
  report_id: string;
  period_type: string;
  frequency: string;
  enabled: boolean;
  note: string;
}

export interface ReportScheduleRequest {
  report_id: string;
  period_type?: string;
  frequency?: string;
  enabled?: boolean;
}

export interface EngineeringReportOptions {
  period_type?: string;
  anchor?: string;
  customer_id?: string;
  team_id?: string;
  include_archived?: boolean;
  include_deleted?: boolean;
  sections?: string[];
}
