import type {
  Project,
  ProjectCreate,
  ProjectDashboard,
  ProjectStatus,
  ProjectUpdate,
} from '../types';
import { apiClient, buildQuery, type ListParams } from '../api/client';

export interface ProjectListParams extends ListParams {
  status?: ProjectStatus;
}

export async function getProjects(params?: ProjectListParams): Promise<Project[]> {
  const { data } = await apiClient.get<Project[]>(`/projects${buildQuery(params)}`);
  return data;
}

export async function getProjectDetail(projectId: string): Promise<ProjectDashboard> {
  const { data } = await apiClient.get<ProjectDashboard>(
    `/projects/${projectId}/detail`,
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

export const projectQueryKeys = {
  all: ['projects'] as const,
  list: (status?: ProjectStatus) =>
    status ? (['projects', { status }] as const) : (['projects'] as const),
  detail: (projectId: string) => ['projects', projectId, 'detail'] as const,
};

export function invalidateProjectDetail(
  queryClient: { invalidateQueries: (options: { queryKey: readonly string[] }) => void },
  projectId: string,
) {
  void queryClient.invalidateQueries({ queryKey: projectQueryKeys.detail(projectId) });
  void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
  void queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
}
