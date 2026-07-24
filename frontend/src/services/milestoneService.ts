import type {
  Milestone,
  MilestoneCreate,
  MilestoneReorderItem,
  MilestoneUpdate,
  ProjectMilestoneSummary,
} from '../types';
import { apiClient, buildQuery, type ListParams } from '../api/client';

export interface MilestoneListParams extends ListParams {
  project_id?: string;
}

export {
  milestoneQueryKeys,
  invalidateMilestoneRelatedQueries,
  invalidateTimesheetRelatedQueries,
} from '../utils/queryInvalidation';

export async function getMilestones(
  params?: MilestoneListParams,
): Promise<Milestone[]> {
  const { data } = await apiClient.get<Milestone[]>(
    `/milestones${buildQuery(params)}`,
  );
  return data;
}

export async function getMilestoneSummary(
  projectId: string,
): Promise<ProjectMilestoneSummary> {
  const { data } = await apiClient.get<ProjectMilestoneSummary>(
    `/milestones/summary/${projectId}`,
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

export async function reorderMilestones(
  projectId: string,
  items: MilestoneReorderItem[],
): Promise<Milestone[]> {
  const { data } = await apiClient.post<Milestone[]>('/milestones/reorder', {
    project_id: projectId,
    items,
  });
  return data;
}

export async function completeMilestone(
  milestoneId: string,
  options?: { qaAcknowledged?: boolean },
): Promise<Milestone> {
  return updateMilestone(milestoneId, {
    status: 'completed',
    progress_percent: 100,
    ...(options?.qaAcknowledged ? { qa_acknowledged: true } : {}),
  });
}

export async function reopenMilestone(milestoneId: string): Promise<Milestone> {
  return updateMilestone(milestoneId, {
    status: 'not_started',
    progress_percent: 0,
    completed_at: null,
    completed_date: null,
  });
}

export async function deleteMilestone(milestoneId: string): Promise<void> {
  await apiClient.delete(`/milestones/${milestoneId}`);
}
