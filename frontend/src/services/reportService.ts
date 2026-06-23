import type {
  CustomerSummaryReportRow,
  DesignerWorkload,
  ProjectHoursReportRow,
} from '../types';
import { apiClient } from '../api/client';

export async function getProjectHoursReport(): Promise<ProjectHoursReportRow[]> {
  const { data } = await apiClient.get<ProjectHoursReportRow[]>(
    '/reports/project-hours',
  );
  return data;
}

export async function getDesignerUtilizationReport(): Promise<DesignerWorkload[]> {
  const { data } = await apiClient.get<DesignerWorkload[]>(
    '/reports/designer-utilization',
  );
  return data;
}

export async function getCustomerSummaryReport(): Promise<CustomerSummaryReportRow[]> {
  const { data } = await apiClient.get<CustomerSummaryReportRow[]>(
    '/reports/customer-summary',
  );
  return data;
}

export const reportQueryKeys = {
  all: ['reports'] as const,
  projectHours: ['reports', 'project-hours'] as const,
  designerUtilization: ['reports', 'designer-utilization'] as const,
  customerSummary: ['reports', 'customer-summary'] as const,
};
