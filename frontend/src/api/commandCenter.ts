import type {
  DecisionCategory,
  EngineeringChange,
  ProjectCommandCenter,
  ProjectDecision,
  ProjectFolderPaths,
} from '../types/CommandCenter';
import { apiClient } from './client';

export async function fetchProjectCommandCenter(projectId: string): Promise<ProjectCommandCenter> {
  const { data } = await apiClient.get<ProjectCommandCenter>(
    `/projects/${projectId}/command-center`,
  );
  return data;
}

export async function cloneProject(projectId: string) {
  const { data } = await apiClient.post(`/projects/${projectId}/clone`);
  return data;
}

export async function updateProjectFolders(
  projectId: string,
  payload: Partial<ProjectFolderPaths>,
): Promise<ProjectFolderPaths> {
  const { data } = await apiClient.patch<ProjectFolderPaths>(
    `/projects/${projectId}/folders`,
    payload,
  );
  return data;
}

export async function createProjectDecision(
  projectId: string,
  payload: { category: DecisionCategory; comment: string; milestone_id?: string | null },
): Promise<ProjectDecision> {
  const { data } = await apiClient.post<ProjectDecision>(
    `/projects/${projectId}/decisions`,
    payload,
  );
  return data;
}

export async function updateProjectDecision(
  projectId: string,
  decisionId: string,
  payload: Partial<{ category: DecisionCategory; comment: string; milestone_id: string | null }>,
): Promise<ProjectDecision> {
  const { data } = await apiClient.patch<ProjectDecision>(
    `/projects/${projectId}/decisions/${decisionId}`,
    payload,
  );
  return data;
}

export async function deleteProjectDecision(projectId: string, decisionId: string) {
  await apiClient.delete(`/projects/${projectId}/decisions/${decisionId}`);
}

export async function createEngineeringChange(
  projectId: string,
  payload: { ec_number: string; title: string; hours?: number },
): Promise<EngineeringChange> {
  const { data } = await apiClient.post<EngineeringChange>(
    `/projects/${projectId}/engineering-changes`,
    payload,
  );
  return data;
}

export async function updateEngineeringChange(
  projectId: string,
  ecId: string,
  payload: Partial<{ ec_number: string; title: string; status: 'open' | 'closed'; hours: number }>,
): Promise<EngineeringChange> {
  const { data } = await apiClient.patch<EngineeringChange>(
    `/projects/${projectId}/engineering-changes/${ecId}`,
    payload,
  );
  return data;
}

export const commandCenterQueryKeys = {
  detail: (projectId: string) => ['projects', projectId, 'command-center'] as const,
};
