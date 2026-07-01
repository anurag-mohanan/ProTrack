import type { DesignerWorkload } from './Dashboard';

export interface ProjectHoursReportRow {
  project_id: string;
  tool_number: string;
  part_description: string;
  customer_name: string;
  quoted_hours: number;
  actual_hours: number;
  hours_variance: number;
  status: string;
}

export interface CustomerSummaryReportRow {
  customer_id: string;
  customer_name: string;
  project_count: number;
  total_quoted_hours: number;
  total_actual_hours: number;
  hours_variance: number;
}

export interface ProductiveHoursReportRow {
  project_id: string | null;
  tool_number: string | null;
  customer_name: string | null;
  task_type_name: string | null;
  total_hours: number;
  billable_hours: number;
  non_billable_hours: number;
}

export interface NonProductiveHoursReportRow {
  non_productive_code: string;
  description: string;
  customer_name: string | null;
  total_hours: number;
}

export interface BillableUtilizationReportRow {
  user_id: string;
  designer_name: string;
  billable_hours: number;
  non_billable_hours: number;
  np_hours: number;
  billable_percent: number;
  non_billable_percent: number;
}

export interface MonthlyNpTrendReportRow {
  month: string;
  total_np_hours: number;
}

export type { DesignerWorkload };
