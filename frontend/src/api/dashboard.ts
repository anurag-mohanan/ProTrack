import type {
  DashboardOverview,
  DashboardSummary,
  DesignerWorkload,
  ProjectDashboard,
} from '../types';
import { apiClient } from './client';

export async function fetchDashboardOverview(): Promise<DashboardOverview> {
  const { data } = await apiClient.get<DashboardOverview>('/dashboard/overview');
  return data;
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await apiClient.get<DashboardSummary>('/dashboard/summary');
  return data;
}

export async function fetchDesignerWorkload(): Promise<DesignerWorkload[]> {
  const { data } = await apiClient.get<DesignerWorkload[]>('/dashboard/workload');
  return data;
}

export async function fetchProjectDashboard(
  projectId: string,
): Promise<ProjectDashboard> {
  const { data } = await apiClient.get<ProjectDashboard>(
    `/dashboard/project/${projectId}`,
  );
  return data;
}
