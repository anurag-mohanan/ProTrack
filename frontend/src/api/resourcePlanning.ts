import type {
  ResourceITGaps,
  ResourceITMatrix,
  ResourcePlanningGranularity,
  ResourcePlanningGrid,
} from '../types/ResourcePlanning';
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

export async function fetchResourceItGaps(params?: {
  team_id?: string;
  on_date?: string;
}): Promise<ResourceITGaps> {
  const { data } = await apiClient.get<ResourceITGaps>(
    `/dashboard/resource-planning/it-gaps${buildQuery(params)}`,
  );
  return data;
}

export async function fetchResourceItMatrix(params?: {
  team_id?: string;
  from_date?: string;
  to_date?: string;
}): Promise<ResourceITMatrix> {
  const { data } = await apiClient.get<ResourceITMatrix>(
    `/dashboard/resource-planning/it-matrix${buildQuery(params)}`,
  );
  return data;
}

export const resourcePlanningQueryKeys = {
  grid: (params?: {
    start?: string;
    granularity?: ResourcePlanningGranularity;
    team_id?: string;
  }) => ['resource-planning', 'grid', params ?? {}] as const,
  itGaps: (params?: { team_id?: string; on_date?: string }) =>
    ['resource-planning', 'it-gaps', params ?? {}] as const,
  itMatrix: (params?: { team_id?: string; from_date?: string; to_date?: string }) =>
    ['resource-planning', 'it-matrix', params ?? {}] as const,
};
