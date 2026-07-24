/**
 * Calendar-month locking for timesheet editing.
 *
 * Business rule: editable while the month is the current month or within the
 * previous N calendar months (org policy). Only older months are hard-locked.
 * Soft-lock warns on the oldest still-editable month.
 */

export const DEFAULT_EDITABLE_MONTHS_BACK = 2;

/** @deprecated Prefer getEditableMonthsBack / policy from settings. */
export const EDITABLE_MONTHS_BACK = DEFAULT_EDITABLE_MONTHS_BACK;

export interface TimesheetLockPolicy {
  editableMonthsBack: number;
  softLockEnabled: boolean;
  hardLockMessage?: string;
  softLockMessage?: string;
}

let cachedPolicy: TimesheetLockPolicy = {
  editableMonthsBack: DEFAULT_EDITABLE_MONTHS_BACK,
  softLockEnabled: true,
};

export function setTimesheetLockPolicy(policy: Partial<TimesheetLockPolicy>): void {
  cachedPolicy = {
    ...cachedPolicy,
    ...policy,
    editableMonthsBack:
      typeof policy.editableMonthsBack === 'number'
        ? Math.max(0, policy.editableMonthsBack)
        : cachedPolicy.editableMonthsBack,
  };
}

export function getTimesheetLockPolicy(): TimesheetLockPolicy {
  return cachedPolicy;
}

export function getEditableMonthsBack(): number {
  return cachedPolicy.editableMonthsBack;
}

export function monthsBeforeCurrent(monthValue: string, today = new Date()): number {
  const [year, month] = monthValue.split('-').map(Number);
  const current = today.getFullYear() * 12 + (today.getMonth() + 1);
  const target = year * 12 + month;
  return current - target;
}

/** Hard-lock months older than the org editable window (admin bypass). */
export function isTimesheetMonthCalendarLocked(
  monthValue: string,
  options?: { adminOverride?: boolean; today?: Date; monthsBack?: number },
): boolean {
  if (options?.adminOverride) return false;
  const window = options?.monthsBack ?? getEditableMonthsBack();
  return monthsBeforeCurrent(monthValue, options?.today) > window;
}

/** Soft-lock: oldest still-editable month (about to archive). */
export function isTimesheetMonthSoftLocked(
  monthValue: string,
  options?: { adminOverride?: boolean; today?: Date; monthsBack?: number },
): boolean {
  if (options?.adminOverride) return false;
  if (!cachedPolicy.softLockEnabled) return false;
  const window = options?.monthsBack ?? getEditableMonthsBack();
  if (window <= 0) return false;
  return monthsBeforeCurrent(monthValue, options?.today) === window;
}

export function isEntryDateCalendarLocked(
  entryDate: string,
  options?: { adminOverride?: boolean; today?: Date; monthsBack?: number },
): boolean {
  const monthValue = entryDate.slice(0, 7);
  return isTimesheetMonthCalendarLocked(monthValue, options);
}
