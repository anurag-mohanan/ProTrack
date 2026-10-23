import type {
  EngineeringDataQuality,
  EngineeringPerformanceParams,
  EngineeringPerformanceReport,
  TemplateLookup,
} from '../types/EngineeringPerformance';
import { ensureArray } from '../types/pagination';
import { getAccessToken } from '../services/authStorage';
import { API_BASE_URL, apiClient, buildQuery } from './client';

function performanceQuery(params: EngineeringPerformanceParams): string {
  return buildQuery({ ...params });
}

export async function fetchEngineeringPerformance(
  params: EngineeringPerformanceParams,
): Promise<EngineeringPerformanceReport> {
  const { data } = await apiClient.get<EngineeringPerformanceReport>(
    `/reports/engineering-performance${performanceQuery(params)}`,
  );
  return data;
}

export async function downloadEngineeringPerformanceExcel(
  params: EngineeringPerformanceParams,
): Promise<void> {
  const token = getAccessToken();
  const response = await fetch(
    `${API_BASE_URL}/reports/engineering-performance/export.xlsx${performanceQuery(params)}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  );
  if (!response.ok) {
    let detail = `Export failed (HTTP ${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      // Non-JSON error body: keep the HTTP status message.
    }
    throw new Error(detail);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? 'Engineering_Performance.xlsx';
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function fetchTemplateLookups(): Promise<TemplateLookup[]> {
  const { data } = await apiClient.get<unknown>('/lookups/project-templates');
  return ensureArray<TemplateLookup>(data);
}

export async function fetchEngineeringDataQuality(): Promise<EngineeringDataQuality> {
  const { data } = await apiClient.get<EngineeringDataQuality>('/reports/engineering-data-quality');
  return data;
}

export const engineeringPerformanceQueryKeys = {
  dataQuality: ['reports', 'engineering-data-quality'] as const,
  report: (params: EngineeringPerformanceParams) =>
    ['reports', 'engineering-performance', params] as const,
  templates: ['lookups', 'project-templates'] as const,
};
