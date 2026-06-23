import type {
  Timesheet,
  TimesheetCreate,
  TimesheetEntry,
  TimesheetEntryCreate,
} from '../types';
import { apiClient, buildQuery, type ListParams } from './client';

export async function fetchTimesheets(params?: ListParams): Promise<Timesheet[]> {
  const { data } = await apiClient.get<Timesheet[]>(
    `/timesheets${buildQuery(params)}`,
  );
  return data;
}

export async function createTimesheet(payload: TimesheetCreate): Promise<Timesheet> {
  const { data } = await apiClient.post<Timesheet>('/timesheets', payload);
  return data;
}

export async function fetchTimesheetEntries(
  params?: ListParams,
): Promise<TimesheetEntry[]> {
  const { data } = await apiClient.get<TimesheetEntry[]>(
    `/timesheet-entries${buildQuery(params)}`,
  );
  return data;
}

export async function createTimesheetEntry(
  payload: TimesheetEntryCreate,
): Promise<TimesheetEntry> {
  const { data } = await apiClient.post<TimesheetEntry>(
    '/timesheet-entries',
    payload,
  );
  return data;
}
