import type { Milestone, MilestoneUpdate } from '../types';
import { apiClient, buildQuery, type ListParams } from './client';

export interface MilestoneListParams extends ListParams {
  project_id?: string;
}

export async function fetchMilestones(
  params?: MilestoneListParams,
): Promise<Milestone[]> {
  const { data } = await apiClient.get<Milestone[]>(
    `/milestones${buildQuery(params)}`,
  );
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
