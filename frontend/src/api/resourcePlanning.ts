import type { ResourcePlanningGranularity, ResourcePlanningGrid } from '../types/ResourcePlanning';
import { apiClient, buildQuery } from './client';

export async function fetchResourcePlanningGrid(params?: {
  start?: string;
  granularity?: ResourcePlanningGranularity;
  team_id?: string;
}): Promise<ResourcePlanningGrid> {
  const { data } = await apiClient.get<ResourcePlanningGrid>(
    `/dashboard/resource-planning/grid${buildQuery(params)}`,
  );
  return data;
}

export async function assignProjectDesigner(payload: {
  project_id: string;
  designer_id: string | null;
}) {
  await apiClient.post('/dashboard/resource-planning/assign', payload);
}

export const resourcePlanningQueryKeys = {
  grid: (params?: {
    start?: string;
    granularity?: ResourcePlanningGranularity;
    team_id?: string;
  }) => ['resource-planning', 'grid', params ?? {}] as const,
};
