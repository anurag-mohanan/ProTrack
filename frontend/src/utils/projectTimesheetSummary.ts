import type { TimesheetEntry } from '../types';
import { isReworkQualityReason } from '../types/TimesheetEntry';
import { toFiniteNumber } from './format';

/** Matches engineering reports Review bucket (Design Review / checking / review). */
export function isCheckingTaskType(taskTypeName: string | null | undefined): boolean {
  const name = (taskTypeName ?? '').trim().toLowerCase();
  if (!name) return false;
  return name.includes('review') || name.includes('check');
}

export interface DesignerHoursBreakdown {
  userId: string;
  userName: string;
  hours: number;
  entryCount: number;
  billableHours: number;
  unbilledHours: number;
  reworkHours: number;
}

export interface ProjectTimesheetSummary {
  totalHours: number;
  billableHours: number;
  unbilledHours: number;
  reworkHours: number;
  checkingHours: number;
  designerCount: number;
  entryCount: number;
  distinctTaskCount: number;
  byDesigner: DesignerHoursBreakdown[];
}

export function summarizeProjectTimesheetEntries(
  entries: TimesheetEntry[],
): ProjectTimesheetSummary {
  const byDesigner = new Map<string, DesignerHoursBreakdown>();
  const tasks = new Set<string>();
  let totalHours = 0;
  let billableHours = 0;
  let unbilledHours = 0;
  let reworkHours = 0;
  let checkingHours = 0;

  for (const entry of entries) {
    const hours = toFiniteNumber(entry.hours);
    totalHours += hours;
    if (entry.is_billable) billableHours += hours;
    else unbilledHours += hours;
    if (isReworkQualityReason(entry.contribution_reason)) {
      reworkHours += hours;
    }
    if (entry.work_category === 'productive' && isCheckingTaskType(entry.task_type_name)) {
      checkingHours += hours;
    }
    if (entry.work_category === 'productive' && entry.task_type_name) {
      tasks.add(entry.task_type_name.trim());
    } else if (entry.work_category === 'non_productive') {
      const label =
        entry.non_productive_description?.trim() ||
        entry.non_productive_code?.trim() ||
        'Non-Productive';
      tasks.add(label);
    }

    const userId = entry.user_id ?? 'unknown';
    const userName = entry.user_name?.trim() || 'Unknown';
    const existing = byDesigner.get(userId);
    if (existing) {
      existing.hours += hours;
      existing.entryCount += 1;
      if (entry.is_billable) existing.billableHours += hours;
      else existing.unbilledHours += hours;
      if (isReworkQualityReason(entry.contribution_reason)) existing.reworkHours += hours;
    } else {
      byDesigner.set(userId, {
        userId,
        userName,
        hours,
        entryCount: 1,
        billableHours: entry.is_billable ? hours : 0,
        unbilledHours: entry.is_billable ? 0 : hours,
        reworkHours: isReworkQualityReason(entry.contribution_reason) ? hours : 0,
      });
    }
  }

  const designers = [...byDesigner.values()].sort(
    (a, b) => b.hours - a.hours || a.userName.localeCompare(b.userName),
  );

  return {
    totalHours,
    billableHours,
    unbilledHours,
    reworkHours,
    checkingHours,
    designerCount: designers.length,
    entryCount: entries.length,
    distinctTaskCount: tasks.size,
    byDesigner: designers,
  };
}

export function sortProjectTimesheetEntries(entries: TimesheetEntry[]): TimesheetEntry[] {
  return [...entries].sort((a, b) => {
    const dateCmp = b.entry_date.localeCompare(a.entry_date);
    if (dateCmp !== 0) return dateCmp;
    const userCmp = (a.user_name ?? '').localeCompare(b.user_name ?? '');
    if (userCmp !== 0) return userCmp;
    return (a.task_type_name ?? '').localeCompare(b.task_type_name ?? '');
  });
}
