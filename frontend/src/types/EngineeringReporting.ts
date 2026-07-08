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
  team_name?: string | null;
  productive_hours: number;
  non_productive_hours: number;
  leave_days: number;
  total_hours: number;
  billable_percent: number;
  utilization_percent: number;
  project_count: number;
  customer_count: number;
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
}

export interface EngineeringReportPayload {
  report_id: string;
  period: ReportPeriod;
  company_name: string;
  executive: ExecutiveSummary;
  designer_productivity: DesignerProductivityRow[];
  designer_tool_breakdown: unknown[];
  tool_hours: ToolHoursRow[];
  customer_summary: CustomerHoursRow[];
  team_summary: unknown[];
  function_hours: unknown[];
  np_analysis: unknown[];
  leave_analysis: unknown[];
  quoted_vs_actual: unknown[];
  project_performance: unknown[];
  detailed_entries: unknown[];
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
  include_archived?: boolean;
  include_deleted?: boolean;
}
