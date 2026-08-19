import type {
  Timesheet,
  TimesheetCreate,
  TimesheetEntry,
  TimesheetEntryCreate,
} from '../types';
import type { ContributionReason, PostCompletionWorkType, TimesheetOverviewContext } from '../types/TimesheetEntry';
import { apiClient, buildQuery, type ListParams, API_BASE_URL } from './client';
import { getAccessToken } from '../services/authStorage';

export interface TimesheetEntryBulkUpsert {
  id?: string | null;
  timesheet_id: string;
  work_category?: 'productive' | 'non_productive';
  project_id?: string | null;
  customer_id?: string | null;
  task_type_id?: string | null;
  milestone_id?: string | null;
  non_productive_code_id?: string | null;
  entry_date: string;
  hours: number;
  is_billable?: boolean;
  description?: string | null;
  contribution_reason?: ContributionReason | null;
  post_completion_type?: PostCompletionWorkType | null;
}

export interface TimesheetEntryBulkRequest {
  upserts: TimesheetEntryBulkUpsert[];
  deletes: string[];
}

export interface TimesheetEntryBulkResponse {
  upserted: TimesheetEntry[];
  deleted: string[];
}

export async function fetchTimesheets(
  params?: ListParams & {
    month?: string;
    period_start?: string;
    period_end?: string;
  },
): Promise<Timesheet[]> {
  const { data } = await apiClient.get<Timesheet[]>(
    `/timesheets${buildQuery(params)}`,
  );
  return data;
}

/** Load every page for a month / filter — avoids silent truncation at API limit. */
export async function fetchAllTimesheets(
  params?: ListParams & {
    month?: string;
    period_start?: string;
    period_end?: string;
  },
): Promise<Timesheet[]> {
  const pageSize = Math.min(params?.limit ?? 2000, 10000);
  const all: Timesheet[] = [];
  let skip = params?.skip ?? 0;
  for (let page = 0; page < 50; page += 1) {
    const batch = await fetchTimesheets({ ...params, skip, limit: pageSize });
    all.push(...batch);
    if (batch.length < pageSize) break;
    skip += pageSize;
  }
  return all;
}

export async function fetchTimesheetOverview(params?: {
  month?: string;
  period_start?: string;
  period_end?: string;
}): Promise<TimesheetOverviewContext> {
  const { data } = await apiClient.get<TimesheetOverviewContext>('/timesheets/overview', {
    params: params?.period_start && params?.period_end
      ? { period_start: params.period_start, period_end: params.period_end }
      : params?.month
        ? { month: params.month }
        : undefined,
  });
  return data;
}

export async function downloadDesignerTimesheetExcel(params: {
  userId: string;
  periodStart: string;
  periodEnd: string;
  periodLabel?: string;
}): Promise<void> {
  const token = getAccessToken();
  const query = buildQuery({
    user_id: params.userId,
    period_start: params.periodStart,
    period_end: params.periodEnd,
    period_label: params.periodLabel,
  });
  const response = await fetch(`${API_BASE_URL}/timesheets/export/designer.xlsx${query}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error('Failed to download designer timesheet.');
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? `timesheet-${params.userId}.xlsx`;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function ensureWeekTimesheet(payload: TimesheetCreate): Promise<Timesheet> {
  const { data } = await apiClient.post<Timesheet>('/timesheets/ensure-week', payload);
  return data;
}

export async function createTimesheet(payload: TimesheetCreate): Promise<Timesheet> {
  const { data } = await apiClient.post<Timesheet>('/timesheets', payload);
  return data;
}

export async function fetchTimesheetEntries(
  params?: ListParams & {
    project_id?: string;
    timesheet_id?: string;
    entry_date_from?: string;
    entry_date_to?: string;
    user_id?: string;
  },
): Promise<TimesheetEntry[]> {
  const { data } = await apiClient.get<TimesheetEntry[]>(
    `/timesheet-entries${buildQuery(params)}`,
  );
  return data;
}

/** Paginate until exhausted so org-wide month views never drop designer hours. */
export async function fetchAllTimesheetEntries(
  params?: ListParams & {
    project_id?: string;
    timesheet_id?: string;
    entry_date_from?: string;
    entry_date_to?: string;
    user_id?: string;
  },
): Promise<TimesheetEntry[]> {
  const pageSize = Math.min(params?.limit ?? 2000, 10000);
  const all: TimesheetEntry[] = [];
  let skip = params?.skip ?? 0;
  for (let page = 0; page < 50; page += 1) {
    const batch = await fetchTimesheetEntries({ ...params, skip, limit: pageSize });
    all.push(...batch);
    if (batch.length < pageSize) break;
    skip += pageSize;
  }
  return all;
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

export async function updateTimesheetEntry(
  entryId: string,
  payload: Partial<TimesheetEntryCreate>,
): Promise<TimesheetEntry> {
  const { data } = await apiClient.patch<TimesheetEntry>(
    `/timesheet-entries/${entryId}`,
    payload,
  );
  return data;
}

export async function deleteTimesheetEntry(entryId: string): Promise<void> {
  await apiClient.delete(`/timesheet-entries/${entryId}`);
}

export interface TimesheetEntryDeletionLog {
  id: string;
  entry_id: string;
  designer_user_id: string;
  designer_name: string;
  entry_date: string;
  tool_number: string | null;
  task_name: string | null;
  hours: number;
  is_billable: boolean;
  notes: string | null;
  deleted_by_id: string;
  deleted_by_name: string | null;
  deleted_at: string;
  reason: string;
  restored_at: string | null;
  restored_by_id: string | null;
}

export async function fetchDeletedTimesheetEntries(params?: {
  skip?: number;
  limit?: number;
  include_restored?: boolean;
}): Promise<TimesheetEntryDeletionLog[]> {
  const { data } = await apiClient.get<TimesheetEntryDeletionLog[]>(
    `/timesheet-entries/deleted${buildQuery(params)}`,
  );
  return data;
}

export async function restoreTimesheetEntry(entryId: string): Promise<TimesheetEntry> {
  const { data } = await apiClient.post<TimesheetEntry>(
    `/timesheet-entries/${entryId}/restore`,
  );
  return data;
}

export async function bulkSaveTimesheetEntries(
  payload: TimesheetEntryBulkRequest,
): Promise<TimesheetEntryBulkResponse> {
  const { data } = await apiClient.post<TimesheetEntryBulkResponse>(
    '/timesheet-entries/bulk',
    payload,
  );
  return data;
}
