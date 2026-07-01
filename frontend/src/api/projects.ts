import type { Project, ExecutionStatus, ProjectStage } from '../types';
import { apiClient, buildQuery, type ListParams } from './client';

export interface ProjectListParams extends ListParams {
  execution_status?: ExecutionStatus;
  project_stage?: ProjectStage;
}

export async function fetchProjects(params?: ProjectListParams): Promise<Project[]> {
  const { data } = await apiClient.get<Project[]>(`/projects${buildQuery(params)}`);
  return data;
}

export async function fetchProject(projectId: string): Promise<Project> {
  const { data } = await apiClient.get<Project>(`/projects/${projectId}`);
  return data;
}
