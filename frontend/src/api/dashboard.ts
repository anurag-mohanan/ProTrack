import type {
  DashboardKpis,
  DashboardMyTasks,
  DashboardOverview,
  DashboardSummary,
  DesignerWorkload,
  ProjectAttentionRow,
  ProjectDashboard,
} from '../types';
import type { Activity } from '../types/Workflow';
import { apiClient } from './client';

export async function fetchDashboardKpis(): Promise<DashboardKpis> {
  const { data } = await apiClient.get<DashboardKpis>('/dashboard/kpis');
  return data;
}

export async function fetchAttentionProjects(): Promise<ProjectAttentionRow[]> {
  const { data } = await apiClient.get<ProjectAttentionRow[]>('/dashboard/attention-projects');
  return data;
}

export async function fetchDashboardRecentActivity(): Promise<Activity[]> {
  const { data } = await apiClient.get<Activity[]>('/dashboard/recent-activity');
  return data;
}

export async function fetchDashboardMyTasks(): Promise<DashboardMyTasks> {
  const { data } = await apiClient.get<DashboardMyTasks>('/dashboard/my-tasks');
  return data;
}

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

export const dashboardQueryKeys = {
  all: ['dashboard'] as const,
  summary: ['dashboard', 'summary'] as const,
  kpis: ['dashboard', 'kpis'] as const,
  attentionProjects: ['dashboard', 'attention-projects'] as const,
  recentActivity: ['dashboard', 'recent-activity'] as const,
  myTasks: ['dashboard', 'my-tasks'] as const,
  overview: ['dashboard', 'overview'] as const,
};
