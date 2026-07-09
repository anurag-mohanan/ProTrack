import { apiClient, buildQuery, type ListParams } from './client';
import {
  normalizePaginatedResponse,
  unwrapListResponse,
  type PaginatedResponse,
} from '../types/pagination';
import type {
  ProjectTemplate,
  ProjectTemplateCreatePayload,
  ProjectTemplateDetail,
  ProjectTemplateMatch,
  ProjectTemplateUpdatePayload,
  ProjectType,
} from '../types/ProjectTemplate';

export async function fetchProjectTypes(): Promise<ProjectType[]> {
  const { data } = await apiClient.get<ProjectType[]>('/lookups/project-types');
  return data;
}

export async function fetchAdminProjectTypes(): Promise<ProjectType[]> {
  const { data } = await apiClient.get<ProjectType[]>('/project-types');
  return data;
}

export async function createProjectType(payload: {
  name: string;
  description?: string | null;
  is_active?: boolean;
}): Promise<ProjectType> {
  const { data } = await apiClient.post<ProjectType>('/project-types', payload);
  return data;
}

export async function updateProjectType(
  id: string,
  payload: Partial<{ name: string; description: string | null; is_active: boolean }>,
): Promise<ProjectType> {
  const { data } = await apiClient.patch<ProjectType>(`/project-types/${id}`, payload);
  return data;
}

export async function deleteProjectType(id: string): Promise<void> {
  await apiClient.delete(`/project-types/${id}`);
}

export async function fetchProjectTemplates(params?: ListParams): Promise<ProjectTemplate[]> {
  const { data } = await apiClient.get<ProjectTemplate[] | PaginatedResponse<ProjectTemplate>>(
    `/project-templates${buildQuery({ limit: 500, ...params })}`,
  );
  return unwrapListResponse(data);
}

export async function fetchProjectTemplatesPaginated(
  params?: ListParams,
): Promise<PaginatedResponse<ProjectTemplate>> {
  const { data } = await apiClient.get<ProjectTemplate[] | PaginatedResponse<ProjectTemplate>>(
    `/project-templates${buildQuery(params)}`,
  );
  return normalizePaginatedResponse(data);
}

export async function fetchProjectTemplate(id: string): Promise<ProjectTemplateDetail> {
  const { data } = await apiClient.get<ProjectTemplateDetail>(`/project-templates/${id}`);
  return data;
}

export async function createProjectTemplate(
  payload: ProjectTemplateCreatePayload,
): Promise<ProjectTemplateDetail> {
  const { data } = await apiClient.post<ProjectTemplateDetail>('/project-templates', payload);
  return data;
}

export async function updateProjectTemplate(
  id: string,
  payload: ProjectTemplateUpdatePayload,
): Promise<ProjectTemplateDetail> {
  const { data } = await apiClient.patch<ProjectTemplateDetail>(
    `/project-templates/${id}`,
    payload,
  );
  return data;
}

export async function duplicateProjectTemplate(id: string): Promise<ProjectTemplateDetail> {
  const { data } = await apiClient.post<ProjectTemplateDetail>(
    `/project-templates/${id}/duplicate`,
  );
  return data;
}

export async function deactivateProjectTemplate(id: string): Promise<ProjectTemplate> {
  const { data } = await apiClient.post<ProjectTemplate>(
    `/project-templates/${id}/deactivate`,
  );
  return data;
}

export async function reactivateProjectTemplate(id: string): Promise<ProjectTemplate> {
  const { data } = await apiClient.post<ProjectTemplate>(
    `/project-templates/${id}/reactivate`,
  );
  return data;
}

export async function deleteProjectTemplate(id: string): Promise<void> {
  await apiClient.delete(`/project-templates/${id}`);
}

export async function fetchMatchingProjectTemplates(params: {
  project_type_id: string;
  customer_id: string;
}): Promise<ProjectTemplateMatch[]> {
  const { data } = await apiClient.get<ProjectTemplateMatch[]>(
    `/project-templates/match${buildQuery(params)}`,
  );
  return data;
}
