import type { Milestone, MilestoneCreate, MilestoneUpdate } from '../types';
import { apiClient, buildQuery, type ListParams } from '../api/client';

export interface MilestoneListParams extends ListParams {
  project_id?: string;
}

export { milestoneQueryKeys, invalidateMilestoneRelatedQueries } from '../utils/queryInvalidation';

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

export async function completeMilestone(milestoneId: string): Promise<Milestone> {
  return updateMilestone(milestoneId, { status: 'completed' });
}

export async function reopenMilestone(milestoneId: string): Promise<Milestone> {
  return updateMilestone(milestoneId, {
    status: 'not_started',
    completed_at: null,
  });
}

export async function deleteMilestone(milestoneId: string): Promise<void> {
  await apiClient.delete(`/milestones/${milestoneId}`);
}
