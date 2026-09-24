import { apiClient } from './client';

export const workstationPackageKeys = {
  all: ['workstation-packages'] as const,
  list: (filters?: Record<string, unknown>) =>
    [...workstationPackageKeys.all, 'list', filters ?? {}] as const,
  detail: (id: string) => [...workstationPackageKeys.all, 'detail', id] as const,
  capacity: (onDate?: string) =>
    [...workstationPackageKeys.all, 'capacity', onDate ?? 'today'] as const,
  forUser: (userId: string) => [...workstationPackageKeys.all, 'user', userId] as const,
};

export async function fetchWorkstationPackages(params?: {
  status?: string;
  computer_type?: string;
  shift_id?: string;
  on_date?: string;
  availability?: string;
  min_monitors?: number;
  mouse_3d?: boolean;
}) {
  const { data } = await apiClient.get('/it/workstation-packages', { params });
  return data as Record<string, unknown>[];
}

export async function fetchWorkstationCapacity(on_date?: string) {
  const { data } = await apiClient.get('/it/workstation-packages/capacity', {
    params: on_date ? { on_date } : undefined,
  });
  return data as {
    computer_type: string;
    label: string;
    total: number;
    maintenance: number;
    incomplete: number;
    shifts: { shift_code: string; shift_name: string; available: number; assigned: number }[];
  }[];
}

export async function findAvailableComputer(payload: {
  on_date: string;
  shift_id: string;
  computer_type?: string | null;
  monitor_quantity?: number;
  mouse_3d_required?: boolean;
  user_id?: string | null;
  provisioning_request_id?: string | null;
}) {
  const { data } = await apiClient.post('/it/workstation-packages/find-available', payload);
  return data as {
    exact_matches: Record<string, unknown>[];
    partial_matches: Record<string, unknown>[];
    unavailable_matches: Record<string, unknown>[];
  };
}

export async function createWorkstationPackage(payload: {
  code: string;
  name: string;
  primary_computer_asset_id: string;
  computer_type?: string | null;
  members?: { asset_id: string; role?: string; is_required?: boolean }[];
  notes?: string | null;
}) {
  const { data } = await apiClient.post('/it/workstation-packages', payload);
  return data;
}

export async function assignWorkstationPackage(
  packageId: string,
  payload: {
    user_id: string;
    shift_id: string;
    effective_from?: string | null;
    notes?: string | null;
    force_override?: boolean;
    override_reason?: string | null;
    provisioning_request_id?: string | null;
  },
) {
  const { data } = await apiClient.post(
    `/it/workstation-packages/${packageId}/assign`,
    payload,
  );
  return data as { id: string; package_id: string; status: string };
}

export async function fetchPackagesForUser(userId: string) {
  const { data } = await apiClient.get(`/it/workstation-packages/for-user/${userId}`);
  return data as Record<string, unknown>[];
}
