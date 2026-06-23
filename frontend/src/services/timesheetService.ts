import type { Timesheet, TimesheetCreate, TimesheetUpdate } from '../types';
import { apiClient, buildQuery, type ListParams } from '../api/client';

export async function getTimesheets(params?: ListParams): Promise<Timesheet[]> {
  const { data } = await apiClient.get<Timesheet[]>(
    `/timesheets${buildQuery(params)}`,
  );
  return data;
}

export async function createTimesheet(payload: TimesheetCreate): Promise<Timesheet> {
  const { data } = await apiClient.post<Timesheet>('/timesheets', payload);
  return data;
}

export async function updateTimesheet(
  timesheetId: string,
  payload: TimesheetUpdate,
): Promise<Timesheet> {
  const { data } = await apiClient.patch<Timesheet>(
    `/timesheets/${timesheetId}`,
    payload,
  );
  return data;
}

export async function submitTimesheet(timesheetId: string): Promise<Timesheet> {
  return updateTimesheet(timesheetId, {
    status: 'submitted',
    submitted_at: new Date().toISOString(),
  });
}

export async function approveTimesheet(
  timesheetId: string,
  approverId: string,
): Promise<Timesheet> {
  return updateTimesheet(timesheetId, {
    status: 'approved',
    approved_by: approverId,
    approved_at: new Date().toISOString(),
  });
}

export async function rejectTimesheet(timesheetId: string): Promise<Timesheet> {
  return updateTimesheet(timesheetId, {
    status: 'rejected',
    approved_by: null,
    approved_at: null,
  });
}

export const timesheetQueryKeys = {
  all: ['timesheets'] as const,
  entries: (timesheetId?: string) =>
    timesheetId
      ? (['timesheet-entries', timesheetId] as const)
      : (['timesheet-entries'] as const),
};
