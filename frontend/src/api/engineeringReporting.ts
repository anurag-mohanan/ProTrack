import type {
  DesignerTeamTimesheetPayload,
  EngineeringReportOptions,
  EngineeringReportPayload,
  ReportCatalog,
  ReportCatalogEntry,
  ReportScheduleEntry,
  ReportScheduleRequest,
} from '../types/EngineeringReporting';
import { ensureArray } from '../types/pagination';
import { apiClient, buildQuery } from './client';
import { getAccessToken } from '../services/authStorage';
import { API_BASE_URL } from './client';

function reportQuery(options?: EngineeringReportOptions): string {
  return buildQuery({
    period_type: options?.period_type,
    anchor: options?.anchor,
    customer_id: options?.customer_id,
    team_id: options?.team_id,
    include_archived: options?.include_archived,
    include_deleted: options?.include_deleted,
  });
}

export function isDesignerTeamTimesheetReport(reportId: string): boolean {
  return (
    reportId === 'weekly-timesheet' ||
    reportId === 'monthly-timesheet' ||
    reportId === 'quarterly-timesheet' ||
    reportId === 'yearly-timesheet'
  );
}

export async function fetchEngineeringReportCatalog(): Promise<ReportCatalog> {
  const { data } = await apiClient.get<ReportCatalog | ReportCatalogEntry[]>('/reports/catalog');
  if (Array.isArray(data)) {
    return { reports: data };
  }
  return {
    reports: ensureArray((data as ReportCatalog | undefined)?.reports),
  };
}

export async function fetchEngineeringReportPreview(
  reportId: string,
  options?: EngineeringReportOptions,
): Promise<EngineeringReportPayload | DesignerTeamTimesheetPayload> {
  const { data } = await apiClient.get<EngineeringReportPayload | DesignerTeamTimesheetPayload>(
    `/reports/engine/${reportId}/preview${reportQuery(options)}`,
  );
  return data;
}

export async function downloadEngineeringReportExcel(
  reportId: string,
  options?: EngineeringReportOptions,
): Promise<void> {
  const token = getAccessToken();
  const response = await fetch(
    `${API_BASE_URL}/reports/engine/${reportId}/export.xlsx${reportQuery(options)}`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  );
  if (!response.ok) {
    throw new Error('Failed to download engineering report.');
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? `${reportId}.xlsx`;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function fetchEngineeringReportSchedules(): Promise<ReportScheduleEntry[]> {
  const { data } = await apiClient.get<unknown>('/reports/schedules');
  return ensureArray<ReportScheduleEntry>(data);
}

export async function saveEngineeringReportSchedule(
  payload: ReportScheduleRequest,
): Promise<ReportScheduleEntry> {
  const { data } = await apiClient.put<ReportScheduleEntry>('/reports/schedules', payload);
  return data;
}

export const engineeringReportQueryKeys = {
  catalog: ['engineering-reports', 'catalog'] as const,
  preview: (reportId: string, options?: EngineeringReportOptions) =>
    ['engineering-reports', 'preview', reportId, options] as const,
  schedules: ['engineering-reports', 'schedules'] as const,
};
