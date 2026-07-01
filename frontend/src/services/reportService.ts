import type {
  BillableUtilizationReportRow,
  CustomerSummaryReportRow,
  DesignerWorkload,
  MonthlyNpTrendReportRow,
  NonProductiveHoursReportRow,
  ProductiveHoursReportRow,
  ProjectHoursReportRow,
} from '../types';
import { apiClient, buildQuery } from '../api/client';

export interface ReportOptions {
  include_archived?: boolean;
  include_deleted?: boolean;
}

function reportQuery(options?: ReportOptions) {
  return buildQuery({
    include_archived: options?.include_archived,
    include_deleted: options?.include_deleted,
  });
}

export async function getProjectHoursReport(
  options?: ReportOptions,
): Promise<ProjectHoursReportRow[]> {
  const { data } = await apiClient.get<ProjectHoursReportRow[]>(
    `/reports/project-hours${reportQuery(options)}`,
  );
  return data;
}

export async function getDesignerUtilizationReport(): Promise<DesignerWorkload[]> {
  const { data } = await apiClient.get<DesignerWorkload[]>(
    '/reports/designer-utilization',
  );
  return data;
}

export async function getCustomerSummaryReport(
  options?: ReportOptions,
): Promise<CustomerSummaryReportRow[]> {
  const { data } = await apiClient.get<CustomerSummaryReportRow[]>(
    `/reports/customer-summary${reportQuery(options)}`,
  );
  return data;
}

export async function getProductiveHoursReport(): Promise<ProductiveHoursReportRow[]> {
  const { data } = await apiClient.get<ProductiveHoursReportRow[]>('/reports/productive-hours');
  return data;
}

export async function getNonProductiveHoursReport(): Promise<NonProductiveHoursReportRow[]> {
  const { data } = await apiClient.get<NonProductiveHoursReportRow[]>(
    '/reports/non-productive-hours',
  );
  return data;
}

export async function getBillableUtilizationReport(): Promise<BillableUtilizationReportRow[]> {
  const { data } = await apiClient.get<BillableUtilizationReportRow[]>(
    '/reports/billable-utilization',
  );
  return data;
}

export async function getMonthlyNpTrendsReport(): Promise<MonthlyNpTrendReportRow[]> {
  const { data } = await apiClient.get<MonthlyNpTrendReportRow[]>(
    '/reports/monthly-np-trends',
  );
  return data;
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
};
