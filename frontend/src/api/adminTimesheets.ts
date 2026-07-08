import { apiClient } from './client';

export interface TimesheetRecalculationReport {
  users_checked: number;
  months_recalculated: number;
  entries_scanned: number;
  projects_recalculated: number;
  errors_fixed: number;
  warnings: string[];
  execution_ms: number;
}

export async function recalculateTimesheets(): Promise<TimesheetRecalculationReport> {
  const response = await apiClient.post<TimesheetRecalculationReport>(
    '/admin/timesheets/recalculate',
  );
  return response.data;
}
