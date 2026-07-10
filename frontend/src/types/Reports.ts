import type { ExecutionStatus, ProjectStage } from './common';
import type { DesignerWorkload } from './Dashboard';

export interface ProjectHoursReportRow {
  project_id: string;
  tool_number: string;
  part_description: string;
  customer_name: string;
  quoted_hours: number;
  actual_hours: number;
  hours_variance: number;
  execution_status: ExecutionStatus;
  project_stage: ProjectStage;
  contributors?: import('./TimesheetEntry').ProjectContributorSummary[];
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

export interface NpHoursByDesignerReportRow {
  user_id: string;
  designer_name: string;
  total_np_hours: number;
}

export interface BillableVsNonBillableReportRow {
  billable_hours: number;
  non_billable_hours: number;
  np_hours: number;
  leave_days: number;
  billable_percent: number;
  non_billable_percent: number;
}

export interface TopNpActivityReportRow {
  non_productive_code: string;
  description: string;
  total_hours: number;
  entry_count: number;
}

export interface ProjectPortfolioReportRow {
  project_id: string;
  tool_number: string;
  customer_name: string;
  project_stage: ProjectStage;
  execution_status: ExecutionStatus;
  due_date: string;
  health: string;
}

export interface ProjectStageSummaryRow {
  project_stage: ProjectStage;
  project_count: number;
}

export interface ExecutionStatusSummaryRow {
  execution_status: ExecutionStatus;
  project_count: number;
}

export interface TimesheetExportReportRow {
  entry_date: string;
  employee_name: string;
  team_name?: string | null;
  customer_name?: string | null;
  tool_number?: string | null;
  task_name?: string | null;
  hours: number;
  is_billable: boolean;
  work_category: string;
}

export type { DesignerWorkload };

export interface ProjectsByTeamReportRow {
  team_id: string;
  team_name: string;
  team_colour: string;
  project_count: number;
}

export interface HoursByTeamReportRow {
  team_id: string;
  team_name: string;
  quoted_hours: number;
  actual_hours: number;
  hours_variance: number;
}

export interface QuotedVsActualByTeamReportRow {
  team_id: string;
  team_name: string;
  quoted_hours: number;
  actual_hours: number;
  variance_hours: number;
  variance_percent: number;
}

export interface TeamUtilizationReportRow {
  team_id: string | null;
  team_name: string;
  member_count: number;
  allocated_hours: number;
  actual_hours: number;
  utilization_percent: number;
}

export interface CustomerByTeamReportRow {
  team_id: string;
  team_name: string;
  customer_id: string;
  customer_name: string;
  project_count: number;
}

export interface DesignerByTeamReportRow {
  team_id: string;
  team_name: string;
  user_id: string;
  user_name: string;
  role_within_team: string | null;
}

export interface TeamProfitabilityReportRow {
  team_id: string;
  team_name: string;
  quoted_hours: number;
  actual_hours: number;
  margin_hours: number;
  margin_percent: number;
}

export interface MonthlyTeamSummaryRow {
  team_id: string;
  team_name: string;
  year: number;
  month: number;
  actual_hours: number;
}
