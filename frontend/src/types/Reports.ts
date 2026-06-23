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

export type { DesignerWorkload };
