import type {
  BillableUtilizationReportRow,
  BillableVsNonBillableReportRow,
  CustomerSummaryReportRow,
  DesignerWorkload,
  ExecutionStatusSummaryRow,
  MonthlyNpTrendReportRow,
  NonProductiveHoursReportRow,
  NpHoursByDesignerReportRow,
  ProductiveHoursReportRow,
  ProjectHoursReportRow,
  ProjectPortfolioReportRow,
  ProjectClassificationReport,
  ProjectStageSummaryRow,
  TopNpActivityReportRow,
  ProjectsByTeamReportRow,
  HoursByTeamReportRow,
  QuotedVsActualByTeamReportRow,
  TeamUtilizationReportRow,
  CustomerByTeamReportRow,
  DesignerByTeamReportRow,
  TeamProfitabilityReportRow,
  MonthlyTeamSummaryRow,
  TimesheetExportReportRow,
} from '../types';
import { apiClient, buildQuery } from '../api/client';
import { ensureArray } from '../types/pagination';

export interface ReportOptions {
  include_archived?: boolean;
  include_deleted?: boolean;
  team_id?: string;
  stream_id?: string;
}

function reportQuery(options?: ReportOptions) {
  return buildQuery({
    include_archived: options?.include_archived,
    include_deleted: options?.include_deleted,
    team_id: options?.team_id,
    stream_id: options?.stream_id,
  });
}

export async function getProjectHoursReport(
  options?: ReportOptions,
): Promise<ProjectHoursReportRow[]> {
  const { data } = await apiClient.get<ProjectHoursReportRow[]>(
    `/reports/project-hours${reportQuery(options)}`,
  );
  return ensureArray(data);
}

export async function getDesignerUtilizationReport(): Promise<DesignerWorkload[]> {
  const { data } = await apiClient.get<DesignerWorkload[]>(
    '/reports/designer-utilization',
  );
  return ensureArray(data);
}

export async function getCustomerSummaryReport(
  options?: ReportOptions,
): Promise<CustomerSummaryReportRow[]> {
  const { data } = await apiClient.get<CustomerSummaryReportRow[]>(
    `/reports/customer-summary${reportQuery(options)}`,
  );
  return ensureArray(data);
}

export async function getProductiveHoursReport(): Promise<ProductiveHoursReportRow[]> {
  const { data } = await apiClient.get<ProductiveHoursReportRow[]>('/reports/productive-hours');
  return ensureArray(data);
}

export async function getNonProductiveHoursReport(): Promise<NonProductiveHoursReportRow[]> {
  const { data } = await apiClient.get<NonProductiveHoursReportRow[]>(
    '/reports/non-productive-hours',
  );
  return ensureArray(data);
}

export async function getBillableUtilizationReport(): Promise<BillableUtilizationReportRow[]> {
  const { data } = await apiClient.get<BillableUtilizationReportRow[]>(
    '/reports/billable-utilization',
  );
  return ensureArray(data);
}

export async function getMonthlyNpTrendsReport(): Promise<MonthlyNpTrendReportRow[]> {
  const { data } = await apiClient.get<MonthlyNpTrendReportRow[]>(
    '/reports/monthly-np-trends',
  );
  return ensureArray(data);
}

export async function getNpHoursByDesignerReport(): Promise<NpHoursByDesignerReportRow[]> {
  const { data } = await apiClient.get<NpHoursByDesignerReportRow[]>(
    '/reports/np-hours-by-designer',
  );
  return ensureArray(data);
}

export async function getBillableVsNonBillableReport(): Promise<BillableVsNonBillableReportRow> {
  const { data } = await apiClient.get<BillableVsNonBillableReportRow>(
    '/reports/billable-vs-non-billable',
  );
  return data;
}

export async function getTopNpActivitiesReport(): Promise<TopNpActivityReportRow[]> {
  const { data } = await apiClient.get<TopNpActivityReportRow[]>(
    '/reports/top-np-activities',
  );
  return ensureArray(data);
}

export async function getProjectPortfolioReport(
  options?: ReportOptions,
): Promise<ProjectPortfolioReportRow[]> {
  const { data } = await apiClient.get<ProjectPortfolioReportRow[]>(
    `/reports/project-portfolio${reportQuery(options)}`,
  );
  return ensureArray(data);
}

export async function getProjectClassificationReport(
  options?: ReportOptions,
): Promise<ProjectClassificationReport> {
  const { data } = await apiClient.get<ProjectClassificationReport>(
    `/reports/project-classification${reportQuery(options)}`,
  );
  return data;
}

export async function getProjectStageSummaryReport(
  options?: ReportOptions,
): Promise<ProjectStageSummaryRow[]> {
  const { data } = await apiClient.get<ProjectStageSummaryRow[]>(
    `/reports/project-stage-summary${reportQuery(options)}`,
  );
  return ensureArray(data);
}

export async function getExecutionStatusSummaryReport(
  options?: ReportOptions,
): Promise<ExecutionStatusSummaryRow[]> {
  const { data } = await apiClient.get<ExecutionStatusSummaryRow[]>(
    `/reports/execution-status-summary${reportQuery(options)}`,
  );
  return ensureArray(data);
}

export async function getProjectsByTeamReport(
  options?: ReportOptions,
): Promise<ProjectsByTeamReportRow[]> {
  const { data } = await apiClient.get<ProjectsByTeamReportRow[]>(
    `/reports/projects-by-team${reportQuery(options)}`,
  );
  return ensureArray(data);
}

export async function getHoursByTeamReport(
  options?: ReportOptions,
): Promise<HoursByTeamReportRow[]> {
  const { data } = await apiClient.get<HoursByTeamReportRow[]>(
    `/reports/hours-by-team${reportQuery(options)}`,
  );
  return ensureArray(data);
}

export async function getQuotedVsActualByTeamReport(
  options?: ReportOptions,
): Promise<QuotedVsActualByTeamReportRow[]> {
  const { data } = await apiClient.get<QuotedVsActualByTeamReportRow[]>(
    `/reports/quoted-vs-actual-by-team${reportQuery(options)}`,
  );
  return ensureArray(data);
}

export async function getTeamUtilizationReport(): Promise<TeamUtilizationReportRow[]> {
  const { data } = await apiClient.get<TeamUtilizationReportRow[]>(
    '/reports/team-utilization',
  );
  return ensureArray(data);
}

export async function getCustomerByTeamReport(
  options?: ReportOptions,
): Promise<CustomerByTeamReportRow[]> {
  const { data } = await apiClient.get<CustomerByTeamReportRow[]>(
    `/reports/customer-by-team${reportQuery(options)}`,
  );
  return ensureArray(data);
}

export async function getDesignerByTeamReport(): Promise<DesignerByTeamReportRow[]> {
  const { data } = await apiClient.get<DesignerByTeamReportRow[]>(
    '/reports/designer-by-team',
  );
  return ensureArray(data);
}

export async function getTeamProfitabilityReport(
  options?: ReportOptions,
): Promise<TeamProfitabilityReportRow[]> {
  const { data } = await apiClient.get<TeamProfitabilityReportRow[]>(
    `/reports/team-profitability${reportQuery(options)}`,
  );
  return ensureArray(data);
}

export async function getMonthlyTeamSummaryReport(): Promise<MonthlyTeamSummaryRow[]> {
  const { data } = await apiClient.get<MonthlyTeamSummaryRow[]>(
    '/reports/monthly-team-summary',
  );
  return ensureArray(data);
}

export interface TimesheetExportOptions extends ReportOptions {
  period?: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly';
  user_id?: string;
  team_id?: string;
  customer_id?: string;
  project_id?: string;
  task_type_id?: string;
  billable?: 'billable' | 'non_billable';
}

export async function getTimesheetExportReport(
  options?: TimesheetExportOptions,
): Promise<TimesheetExportReportRow[]> {
  const { data } = await apiClient.get<TimesheetExportReportRow[]>(
    `/reports/timesheet-export${buildQuery({ ...(options ?? {}) })}`,
  );
  return ensureArray(data);
}

export const reportQueryKeys = {
  all: ['reports'] as const,
  projectHours: (options?: ReportOptions) =>
    ['reports', 'project-hours', options ?? {}] as const,
  designerUtilization: ['reports', 'designer-utilization'] as const,
  customerSummary: (options?: ReportOptions) =>
    ['reports', 'customer-summary', options ?? {}] as const,
  productiveHours: ['reports', 'productive-hours'] as const,
  nonProductiveHours: ['reports', 'non-productive-hours'] as const,
  billableUtilization: ['reports', 'billable-utilization'] as const,
  monthlyNpTrends: ['reports', 'monthly-np-trends'] as const,
  npHoursByDesigner: ['reports', 'np-hours-by-designer'] as const,
  billableVsNonBillable: ['reports', 'billable-vs-non-billable'] as const,
  topNpActivities: ['reports', 'top-np-activities'] as const,
  projectPortfolio: (options?: ReportOptions) =>
    ['reports', 'project-portfolio', options ?? {}] as const,
  projectClassification: (options?: ReportOptions) =>
    ['reports', 'project-classification', options ?? {}] as const,
  projectStageSummary: (options?: ReportOptions) =>
    ['reports', 'project-stage-summary', options ?? {}] as const,
  executionStatusSummary: (options?: ReportOptions) =>
    ['reports', 'execution-status-summary', options ?? {}] as const,
  teamReports: (options?: ReportOptions) => ['reports', 'team', options ?? {}] as const,
};
