import type {
  ArchivedProjectListItem,
  ExecutionStatus,
  Project,
  ProjectCreate,
  ProjectDashboard,
  ProjectDeleteCheck,
  ProjectLifecycleFilter,
  ProjectStage,
  ProjectUpdate,
} from '../types';
import { apiClient, buildQuery, type ListParams } from '../api/client';

export interface ProjectListParams extends ListParams {
  execution_status?: ExecutionStatus;
  project_stage?: ProjectStage;
  lifecycle?: ProjectLifecycleFilter;
}

export async function getProjects(params?: ProjectListParams): Promise<Project[]> {
  const { data } = await apiClient.get<Project[]>(`/projects${buildQuery(params)}`);
  return data;
}

export async function getArchivedProjects(
  params?: ListParams,
): Promise<ArchivedProjectListItem[]> {
  const { data } = await apiClient.get<ArchivedProjectListItem[]>(
    `/projects/archived${buildQuery(params)}`,
  );
  return data;
}

export async function getDeletedProjects(params?: ListParams): Promise<Project[]> {
  const { data } = await apiClient.get<Project[]>(
    `/projects/deleted${buildQuery(params)}`,
  );
  return data;
}

export async function getProjectDetail(projectId: string): Promise<ProjectDashboard> {
  const { data } = await apiClient.get<ProjectDashboard>(
    `/projects/${projectId}/detail`,
  );
  return data;
}

export async function getProjectDeleteCheck(projectId: string): Promise<ProjectDeleteCheck> {
  const { data } = await apiClient.get<ProjectDeleteCheck>(
    `/projects/${projectId}/delete-check`,
  );
  return data;
}

export async function createProject(payload: ProjectCreate): Promise<Project> {
  const { data } = await apiClient.post<Project>('/projects', payload);
  return data;
}

export async function updateProject(
  projectId: string,
  payload: ProjectUpdate,
): Promise<Project> {
  const { data } = await apiClient.patch<Project>(`/projects/${projectId}`, payload);
  return data;
}

export async function archiveProject(projectId: string): Promise<Project> {
  const { data } = await apiClient.post<Project>(`/projects/${projectId}/archive`);
  return data;
}

export async function restoreProject(projectId: string): Promise<Project> {
  const { data } = await apiClient.post<Project>(`/projects/${projectId}/restore`);
  return data;
}

export async function softDeleteProject(projectId: string): Promise<Project> {
  const { data } = await apiClient.post<Project>(`/projects/${projectId}/soft-delete`);
  return data;
}

export async function restoreDeletedProject(projectId: string): Promise<Project> {
  const { data } = await apiClient.post<Project>(
    `/projects/${projectId}/restore-deleted`,
  );
  return data;
}

export async function permanentDeleteProject(projectId: string): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/permanent`);
}

export const projectQueryKeys = {
  all: ['projects'] as const,
  list: (params?: {
    execution_status?: ExecutionStatus;
    project_stage?: ProjectStage;
    lifecycle?: ProjectLifecycleFilter;
  }) =>
    params ? (['projects', params] as const) : (['projects'] as const),
  archived: ['projects', 'archived'] as const,
  deleted: ['projects', 'deleted'] as const,
  detail: (projectId: string) => ['projects', projectId, 'detail'] as const,
};

export { invalidateProjectCalculationQueries } from '../utils/queryInvalidation';
