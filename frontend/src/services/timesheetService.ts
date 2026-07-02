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
  const { data } = await apiClient.post<Timesheet>(
    `/timesheets/${timesheetId}/submit`,
  );
  return data;
}

export async function approveTimesheet(
  timesheetId: string,
  comments?: string,
): Promise<Timesheet> {
  const { data } = await apiClient.post<Timesheet>(
    `/timesheets/${timesheetId}/approve`,
    { comments: comments ?? null },
  );
  return data;
}

export async function rejectTimesheet(
  timesheetId: string,
  comments: string,
): Promise<Timesheet> {
  const { data } = await apiClient.post<Timesheet>(
    `/timesheets/${timesheetId}/reject`,
    { comments },
  );
  return data;
}

export async function returnTimesheetToDraft(timesheetId: string): Promise<Timesheet> {
  const { data } = await apiClient.post<Timesheet>(
    `/timesheets/${timesheetId}/return-to-draft`,
  );
  return data;
}

export const timesheetQueryKeys = {
  all: ['timesheets'] as const,
  month: (month: string, userId?: string) => ['timesheets', 'month', month, userId] as const,
  monthEntries: (month: string, userId?: string) =>
    ['timesheet-entries', 'month', month, userId] as const,
  entries: (timesheetId?: string) =>
    timesheetId
      ? (['timesheet-entries', timesheetId] as const)
      : (['timesheet-entries'] as const),
};
