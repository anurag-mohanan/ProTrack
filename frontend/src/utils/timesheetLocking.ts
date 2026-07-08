/** Calendar-month locking for timesheet editing. */

export function monthsBeforeCurrent(monthValue: string, today = new Date()): number {
  const [year, month] = monthValue.split('-').map(Number);
  const current = today.getFullYear() * 12 + (today.getMonth() + 1);
  const target = year * 12 + month;
  return current - target;
}

/** Lock months older than the previous calendar month (admin bypass). */
export function isTimesheetMonthCalendarLocked(
  monthValue: string,
  options?: { adminOverride?: boolean; today?: Date },
): boolean {
  if (options?.adminOverride) return false;
  return monthsBeforeCurrent(monthValue, options?.today) >= 2;
}

export function isEntryDateCalendarLocked(
  entryDate: string,
  options?: { adminOverride?: boolean; today?: Date },
): boolean {
  const monthValue = entryDate.slice(0, 7);
  return isTimesheetMonthCalendarLocked(monthValue, options);
}
