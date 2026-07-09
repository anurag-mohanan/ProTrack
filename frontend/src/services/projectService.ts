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
import {
  isPaginatedResponse,
  unwrapListResponse,
  type PaginatedResponse,
} from '../types/pagination';

export interface ProjectListParams extends ListParams {
  execution_status?: ExecutionStatus;
  project_stage?: ProjectStage;
  lifecycle?: ProjectLifecycleFilter;
  customer_ids?: string[];
  team_ids?: string[];
  team_id?: string;
  project_type_id?: string;
  design_leader_id?: string;
  designer_id?: string;
  surfacer_id?: string;
}

export async function getProjects(params?: ProjectListParams): Promise<Project[]> {
  const { data } = await apiClient.get<Project[] | PaginatedResponse<Project>>(
    `/projects${buildQuery(params)}`,
  );
  return unwrapListResponse(data);
}

export async function getProjectsPaginated(
  params?: ProjectListParams,
): Promise<PaginatedResponse<Project>> {
  const { data } = await apiClient.get<Project[] | PaginatedResponse<Project>>(
    `/projects${buildQuery(params)}`,
  );
  if (isPaginatedResponse<Project>(data)) {
    return data;
  }
  return {
    items: data,
    total: data.length,
    page: 1,
    page_size: data.length || params?.page_size || params?.limit || 25,
    pages: 1,
  };
}

export async function getArchivedProjects(
  params?: ListParams,
): Promise<ArchivedProjectListItem[]> {
  const { data } = await apiClient.get<
    ArchivedProjectListItem[] | PaginatedResponse<ArchivedProjectListItem>
  >(`/projects/archived${buildQuery(params)}`);
  return unwrapListResponse(data);
}

export async function getArchivedProjectsPaginated(
  params?: ListParams,
): Promise<PaginatedResponse<ArchivedProjectListItem>> {
  const { data } = await apiClient.get<
    ArchivedProjectListItem[] | PaginatedResponse<ArchivedProjectListItem>
  >(`/projects/archived${buildQuery(params)}`);
  if (isPaginatedResponse<ArchivedProjectListItem>(data)) {
    return data;
  }
  return {
    items: data,
    total: data.length,
    page: 1,
    page_size: data.length || params?.page_size || params?.limit || 25,
    pages: 1,
  };
}

export async function getDeletedProjects(params?: ListParams): Promise<Project[]> {
  const { data } = await apiClient.get<Project[] | PaginatedResponse<Project>>(
    `/projects/deleted${buildQuery(params)}`,
  );
  return unwrapListResponse(data);
}

export async function getDeletedProjectsPaginated(
  params?: ListParams,
): Promise<PaginatedResponse<Project>> {
  const { data } = await apiClient.get<Project[] | PaginatedResponse<Project>>(
    `/projects/deleted${buildQuery(params)}`,
  );
  if (isPaginatedResponse<Project>(data)) {
    return data;
  }
  return {
    items: data,
    total: data.length,
    page: 1,
    page_size: data.length || params?.page_size || params?.limit || 25,
    pages: 1,
  };
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

export async function applyProjectTemplate(
  projectId: string,
  projectTemplateId?: string,
): Promise<Project> {
  const { data } = await apiClient.post<Project>(`/projects/${projectId}/apply-template`, {
    project_template_id: projectTemplateId ?? null,
  });
  return data;
}

export const projectQueryKeys = {
  all: ['projects'] as const,
  list: (params?: ProjectListParams) =>
    params ? (['projects', params] as const) : (['projects'] as const),
  archived: ['projects', 'archived'] as const,
  deleted: ['projects', 'deleted'] as const,
  detail: (projectId: string) => ['projects', projectId, 'detail'] as const,
};

export { invalidateProjectCalculationQueries } from '../utils/queryInvalidation';
