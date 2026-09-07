import type {
  Shift,
  ShiftAssignment,
  ShiftAssignmentBulkPayload,
  ShiftAssignmentBulkResult,
  ShiftAssignmentPayload,
  ShiftCalendar,
  ShiftForUser,
  ShiftPayload,
} from '../types/ResourceShifts';
import { apiClient, buildQuery } from './client';

const BASE = '/resource-planning/shifts';

export async function fetchShifts(params?: { active_only?: boolean }): Promise<Shift[]> {
  const { data } = await apiClient.get<Shift[]>(`${BASE}${buildQuery(params)}`);
  return data;
}

export async function createShift(payload: ShiftPayload): Promise<Shift> {
  const { data } = await apiClient.post<Shift>(BASE, payload);
  return data;
}

export async function updateShift(
  shiftId: string,
  payload: Partial<ShiftPayload>,
): Promise<Shift> {
  const { data } = await apiClient.patch<Shift>(`${BASE}/${shiftId}`, payload);
  return data;
}

export async function fetchShiftAssignments(params?: {
  user_id?: string;
  from?: string;
  to?: string;
  include_inactive?: boolean;
}): Promise<ShiftAssignment[]> {
  const { data } = await apiClient.get<ShiftAssignment[]>(
    `${BASE}/assignments${buildQuery(params)}`,
  );
  return data;
}

export async function createShiftAssignment(
  payload: ShiftAssignmentPayload,
): Promise<ShiftAssignment> {
  const { data } = await apiClient.post<ShiftAssignment>(`${BASE}/assignments`, payload);
  return data;
}

export async function bulkCreateShiftAssignments(
  payload: ShiftAssignmentBulkPayload,
): Promise<ShiftAssignmentBulkResult> {
  const { data } = await apiClient.post<ShiftAssignmentBulkResult>(
    `${BASE}/assignments/bulk`,
    payload,
  );
  return data;
}

export async function endShiftAssignment(
  assignmentId: string,
  effectiveTo: string,
): Promise<ShiftAssignment> {
  const { data } = await apiClient.patch<ShiftAssignment>(
    `${BASE}/assignments/${assignmentId}/end`,
    { effective_to: effectiveTo },
  );
  return data;
}

export async function fetchShiftForUser(
  userId: string,
  date?: string,
): Promise<ShiftForUser> {
  const { data } = await apiClient.get<ShiftForUser>(
    `${BASE}/for-user/${userId}${buildQuery({ date })}`,
  );
  return data;
}

export async function fetchShiftCalendar(params: {
  from: string;
  to: string;
  team_id?: string;
}): Promise<ShiftCalendar> {
  const { data } = await apiClient.get<ShiftCalendar>(`${BASE}/calendar${buildQuery(params)}`);
  return data;
}

export const resourceShiftKeys = {
  all: ['resource-shifts'] as const,
  shifts: (params?: { active_only?: boolean }) =>
    ['resource-shifts', 'masters', params ?? {}] as const,
  assignments: (params?: Record<string, unknown>) =>
    ['resource-shifts', 'assignments', params ?? {}] as const,
  calendar: (params: { from: string; to: string; team_id?: string }) =>
    ['resource-shifts', 'calendar', params] as const,
};
