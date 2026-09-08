import type {
  ResourceITGaps,
  ResourceITMatrix,
  ResourcePlanningGranularity,
  ResourcePlanningGrid,
} from '../types/ResourcePlanning';
import type { ResourcePackage, ResourcePackagePreview } from '../types/itOperations';
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

export type ShiftHierarchyPerson = {
  user_id: string;
  name: string;
  shift_id?: string | null;
  team_id?: string | null;
  team_name?: string | null;
  computer?: {
    computer_id: string;
    computer_name?: string | null;
    asset_id?: string | null;
    asset_number?: string | null;
    asset_status?: string | null;
    assigned_date?: string | null;
  } | null;
  ips: Array<{ id: string; address: string }>;
  software: string[];
  installed: string[];
  missing_software: string[];
  projects: Array<{ id: string; tool_number?: string | null; name?: string | null }>;
  has_shortage: boolean;
};

export type ShiftHierarchyTeam = {
  id: string;
  name: string;
  people_count: number;
  shortage_count: number;
  people: ShiftHierarchyPerson[];
};

export type ShiftHierarchyShift = {
  id: string;
  name: string;
  code?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  people_count: number;
  shortage_count: number;
  teams: ShiftHierarchyTeam[];
};

export type ShiftHierarchyReport = {
  on_date: string;
  shifts: ShiftHierarchyShift[];
  unassigned: {
    people_count: number;
    shortage_count: number;
    people: ShiftHierarchyPerson[];
  };
  totals: {
    employees: number;
    with_computer: number;
    without_computer: number;
    with_shortage: number;
    unassigned_shift: number;
  };
};

export async function fetchShiftHierarchy(params?: {
  team_id?: string;
  on_date?: string;
}): Promise<ShiftHierarchyReport> {
  const { data } = await apiClient.get<ShiftHierarchyReport>(
    `/dashboard/resource-planning/shift-hierarchy${buildQuery(params)}`,
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
  computer_shortage?: number;
  required_license_seats: number;
  estimated_license_cost?: number | string | null;
  estimated_monthly_license_cost?: number | string | null;
  estimated_hardware_cost?: number | string | null;
  currency_code?: string | null;
  software?: Array<{
    software_id: string;
    software_name?: string | null;
    seats_needed: number;
    seats_available?: number;
    seats_shortage?: number;
    has_pool?: boolean;
  }>;
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
  shiftHierarchy: (params?: { team_id?: string; on_date?: string }) =>
    ['resource-planning', 'shift-hierarchy', params ?? {}] as const,
  packages: () => ['resource-planning', 'packages'] as const,
  packagePreview: (packageId: string, userId: string) =>
    ['resource-planning', 'package-preview', packageId, userId] as const,
};

export async function fetchPlanningPackages(): Promise<ResourcePackage[]> {
  const { data } = await apiClient.get<ResourcePackage[]>('/dashboard/resource-planning/packages');
  return data;
}

export async function previewResourcePackage(packageId: string, userId: string): Promise<ResourcePackagePreview> {
  const { data } = await apiClient.post<ResourcePackagePreview>(
    `/dashboard/resource-planning/packages/${packageId}/preview`,
    { user_id: userId },
  );
  return data;
}

export async function assignResourcePackage(
  packageId: string,
  payload: {
    user_id: string;
    asset_ids?: string[];
    license_pool_ids?: string[];
    shift_id?: string | null;
    ip_address_id?: string | null;
    notes?: string;
  },
): Promise<Record<string, unknown>> {
  const { data } = await apiClient.post(
    `/dashboard/resource-planning/packages/${packageId}/assign`,
    payload,
  );
  return data;
}
