import { apiClient } from './client';
import type {
  AllocationCheckRequest,
  AllocationCheckResult,
  AssetSchedule,
  LegacyResolveRequest,
  LegacyReview,
  LicenseSchedule,
  LicenseUsageSession,
  ReservationCreate,
  ResourceReservation,
  SetupAssignRequest,
  SetupAssignResult,
  SharingPolicyRow,
} from '../types/itAllocation';
import type { EmployeeRoster, EmployeeRosterParams } from '../types/ResourceShifts';

const BASE = '/it/allocation';

export const itAllocationKeys = {
  all: ['it-allocation'] as const,
  check: (body: AllocationCheckRequest) => [...itAllocationKeys.all, 'check', body] as const,
  assetSchedule: (id: string, onDate?: string) => [...itAllocationKeys.all, 'asset-schedule', id, onDate] as const,
  licenseSchedule: (id: string, onDate?: string) =>
    [...itAllocationKeys.all, 'license-schedule', id, onDate] as const,
  reservations: (filters: Record<string, string | undefined>) =>
    [...itAllocationKeys.all, 'reservations', filters] as const,
  sessions: (poolId: string) => [...itAllocationKeys.all, 'sessions', poolId] as const,
  legacy: () => [...itAllocationKeys.all, 'legacy'] as const,
  sharingPolicy: () => [...itAllocationKeys.all, 'sharing-policy'] as const,
  employees: (params: EmployeeRosterParams) => [...itAllocationKeys.all, 'employees', params] as const,
};

function clean<T extends object>(body: T): T {
  return Object.fromEntries(
    Object.entries(body).filter(([, value]) => value !== undefined && value !== ''),
  ) as T;
}

export async function checkAllocation(body: AllocationCheckRequest) {
  const { data } = await apiClient.post<AllocationCheckResult>(`${BASE}/check`, clean(body));
  return data;
}

export async function fetchAssetSchedule(assetId: string, onDate?: string) {
  const { data } = await apiClient.get<AssetSchedule>(`${BASE}/schedule/asset/${assetId}`, {
    params: onDate ? { on_date: onDate } : undefined,
  });
  return data;
}

export async function fetchLicenseSchedule(poolId: string, onDate?: string) {
  const { data } = await apiClient.get<LicenseSchedule>(`${BASE}/schedule/license/${poolId}`, {
    params: onDate ? { on_date: onDate } : undefined,
  });
  return data;
}

export async function assignSetup(body: SetupAssignRequest) {
  const { data } = await apiClient.post<SetupAssignResult>(`${BASE}/setup`, clean(body));
  return data;
}

export async function fetchReservations(filters: Record<string, string | undefined> = {}) {
  const { data } = await apiClient.get<ResourceReservation[]>(`${BASE}/reservations`, {
    params: clean(filters),
  });
  return data;
}

export async function createReservation(body: ReservationCreate) {
  const { data } = await apiClient.post<ResourceReservation>(`${BASE}/reservations`, clean(body));
  return data;
}

export async function releaseReservation(id: string, reason?: string) {
  const { data } = await apiClient.post<ResourceReservation>(`${BASE}/reservations/${id}/release`, {
    reason: reason || null,
  });
  return data;
}

export async function fetchLicenseSessions(poolId: string, activeOnly = false) {
  const { data } = await apiClient.get<LicenseUsageSession[]>(`${BASE}/licenses/${poolId}/sessions`, {
    params: { active_only: activeOnly },
  });
  return data;
}

export async function checkoutLicense(poolId: string, body: { user_id: string; notes?: string | null }) {
  const { data } = await apiClient.post<LicenseUsageSession>(`${BASE}/licenses/${poolId}/checkout`, body);
  return data;
}

export async function checkinLicense(sessionId: string) {
  const { data } = await apiClient.post<LicenseUsageSession>(`${BASE}/license-sessions/${sessionId}/checkin`);
  return data;
}

export async function fetchLegacyReview() {
  const { data } = await apiClient.get<LegacyReview>(`${BASE}/legacy`);
  return data;
}

export async function resolveLegacyAssignment(assignmentId: string, body: LegacyResolveRequest) {
  const { data } = await apiClient.post(`${BASE}/legacy/${assignmentId}/resolve`, clean(body));
  return data as { assignment_id: string };
}

export async function fetchAssignableEmployees(params: EmployeeRosterParams = {}) {
  const { data } = await apiClient.get<EmployeeRoster>(`${BASE}/employees`, { params: clean(params) });
  return data;
}

export async function fetchSharingPolicy() {
  const { data } = await apiClient.get<SharingPolicyRow[]>(`${BASE}/sharing-policy`);
  return data;
}

export async function updateSharingPolicy(
  assetTypeId: string,
  body: { is_shareable?: boolean | null; requires_shift?: boolean | null },
) {
  const { data } = await apiClient.put<SharingPolicyRow>(`${BASE}/sharing-policy/${assetTypeId}`, body);
  return data;
}
