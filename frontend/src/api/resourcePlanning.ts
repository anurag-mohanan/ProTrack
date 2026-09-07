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

export type DataQualityIssue = {
  code: string;
  severity: string;
  domain: string;
  title: string;
  count: number;
  samples: Array<Record<string, unknown>>;
  repair_code?: string | null;
};

export type DataQualityReport = {
  generated_at: string;
  totals: {
    issue_types: number;
    error: number;
    warning: number;
    info: number;
    computers_total: number;
  };
  issues: DataQualityIssue[];
  open_issues: DataQualityIssue[];
  repairs: Array<{
    code: string;
    label: string;
    available: boolean;
    endpoint: string;
    permission: string;
  }>;
  computer_report?: Record<string, unknown>;
};

export async function fetchResourceDataQuality(): Promise<DataQualityReport> {
  const { data } = await apiClient.get<DataQualityReport>(
    '/dashboard/resource-planning/data-quality',
  );
  return data;
}

export type ComputersByShiftRow = {
  computer_id: string;
  asset_id: string;
  computer_name: string;
  asset_number?: string | null;
  status?: string | null;
  location?: string | null;
  is_open?: boolean;
  assigned_to_user_id?: string | null;
  assigned_to_name?: string | null;
  assigned_to_team?: string | null;
  assigned_date?: string | null;
  current_shift_code?: string | null;
  current_shift_name?: string | null;
  current_shift_display?: string | null;
  next_shift_code?: string | null;
  next_shift_name?: string | null;
  next_shift_display?: string | null;
  next_change_date?: string | null;
  previous_user_id?: string | null;
  previous_user_name?: string | null;
  other_shift_user_id?: string | null;
  other_shift_user_name?: string | null;
  other_shift_code?: string | null;
  other_shift_name?: string | null;
  other_shift_display?: string | null;
  is_shared_candidate?: boolean;
  data_quality_flags?: string[];
};

export type ComputersByShiftReport = {
  on_date: string;
  team_id?: string | null;
  summary: {
    open: number;
    maintenance: number;
    retired: number;
    assigned_with_shift: number;
    assigned_without_shift: number;
    shared_candidates: number;
  };
  open_computers: ComputersByShiftRow[];
  maintenance_computers: ComputersByShiftRow[];
  shifts: Array<{
    shift_id: string;
    shift_code: string;
    shift_name: string;
    shift_display: string;
    assigned_count: number;
    computers: ComputersByShiftRow[];
  }>;
  assigned_without_shift: ComputersByShiftRow[];
  shared_computers: ComputersByShiftRow[];
};

export async function fetchComputersByShift(params?: {
  team_id?: string;
  on_date?: string;
}): Promise<ComputersByShiftReport> {
  const { data } = await apiClient.get<ComputersByShiftReport>(
    `/dashboard/resource-planning/computers-by-shift${buildQuery(params)}`,
  );
  return data;
}

export async function fetchHireImpact(params: {
  headcount: number;
  team_id?: string;
}): Promise<{
  headcount: number;
  team_id?: string | null;
  required_computers: number;
  spare_computers: number;
  computers_to_procure: number;
  required_license_seats: number;
  estimated_license_cost?: number | string | null;
  estimated_monthly_license_cost?: number | string | null;
  assumptions?: string[];
  warnings?: string[];
}> {
  const { data } = await apiClient.get(`/finance/hire-impact${buildQuery(params)}`);
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
  dataQuality: () => ['resource-planning', 'data-quality'] as const,
  computersByShift: (params?: { team_id?: string; on_date?: string }) =>
    ['resource-planning', 'computers-by-shift', params ?? {}] as const,
};
