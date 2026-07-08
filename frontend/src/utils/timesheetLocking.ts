/**
 * Calendar-month locking for timesheet editing.
 *
 * Business rule: a timesheet is editable while its month is the current month
 * or within the previous two calendar months. Only months older than two
 * months are locked. Workflow status (submitted/approved) does NOT lock.
 */

// Months that stay editable, counting back from the current month.
// 0 = current, 1 = previous, 2 = two months ago. 3+ is locked.
export const EDITABLE_MONTHS_BACK = 2;

export function monthsBeforeCurrent(monthValue: string, today = new Date()): number {
  const [year, month] = monthValue.split('-').map(Number);
  const current = today.getFullYear() * 12 + (today.getMonth() + 1);
  const target = year * 12 + month;
  return current - target;
}

/** Lock months older than two calendar months (admin bypass). */
export function isTimesheetMonthCalendarLocked(
  monthValue: string,
  options?: { adminOverride?: boolean; today?: Date },
): boolean {
  if (options?.adminOverride) return false;
  return monthsBeforeCurrent(monthValue, options?.today) > EDITABLE_MONTHS_BACK;
}

export function isEntryDateCalendarLocked(
  entryDate: string,
  options?: { adminOverride?: boolean; today?: Date },
): boolean {
  const monthValue = entryDate.slice(0, 7);
  return isTimesheetMonthCalendarLocked(monthValue, options);
}
