import type { Milestone, MilestoneCreate, MilestoneUpdate } from '../types';
import { apiClient, buildQuery, type ListParams } from '../api/client';

export interface MilestoneListParams extends ListParams {
  project_id?: string;
}

export async function getMilestones(
  params?: MilestoneListParams,
): Promise<Milestone[]> {
  const { data } = await apiClient.get<Milestone[]>(
    `/milestones${buildQuery(params)}`,
  );
  return data;
}

export async function createMilestone(payload: MilestoneCreate): Promise<Milestone> {
  const { data } = await apiClient.post<Milestone>('/milestones', payload);
  return data;
}

export async function updateMilestone(
  milestoneId: string,
  payload: MilestoneUpdate,
): Promise<Milestone> {
  const { data } = await apiClient.patch<Milestone>(
    `/milestones/${milestoneId}`,
    payload,
  );
  return data;
}

export async function deleteMilestone(milestoneId: string): Promise<void> {
  await apiClient.delete(`/milestones/${milestoneId}`);
}

export const milestoneQueryKeys = {
  all: ['milestones'] as const,
  byProject: (projectId: string) => ['milestones', projectId] as const,
};
