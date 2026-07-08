/**
 * Format a Date to an ISO date (YYYY-MM-DD) using LOCAL calendar fields.
 * Avoids the UTC shift from Date.toISOString() that moves dates back a day
 * for users in positive-offset timezones (e.g. IST +5:30).
 */
export function formatLocalIso(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function weekStartMonday(value: string | Date): string {
  const copy = new Date(typeof value === 'string' ? `${value}T12:00:00` : value);
  const day = copy.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  copy.setDate(copy.getDate() + diff);
  return formatLocalIso(copy);
}

export function monthBounds(monthValue: string): { start: string; end: string; days: string[] } {
  const [year, month] = monthValue.split('-').map(Number);
  const startDate = new Date(year, month - 1, 1);
  const endDate = new Date(year, month, 0);
  const days: string[] = [];
  for (let day = 1; day <= endDate.getDate(); day += 1) {
    days.push(formatLocalIso(new Date(year, month - 1, day)));
  }
  return {
    start: formatLocalIso(startDate),
    end: formatLocalIso(endDate),
    days,
  };
}

export function dayName(isoDate: string): string {
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' });
}

export function isWeekend(isoDate: string): boolean {
  const day = new Date(`${isoDate}T12:00:00`).getDay();
  return day === 0 || day === 6;
}

export function countWorkingDays(
  days: string[],
  holidayDates: Set<string>,
): number {
  return days.filter((day) => !isWeekend(day) && !holidayDates.has(day)).length;
}

export function formatMonthLabel(monthValue: string): string {
  const [year, month] = monthValue.split('-').map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  });
}

export function shiftMonth(monthValue: string, delta: number): string {
  const [year, month] = monthValue.split('-').map(Number);
  const date = new Date(year, month - 1 + delta, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

export function currentMonthValue(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

export function todayIsoDate(): string {
  return formatLocalIso(new Date());
}

/**
 * ============================================================================
 * CENTRAL TIMESHEET CALCULATION (single source of truth on the frontend)
 * ----------------------------------------------------------------------------
 * Every timesheet total shown in the app (Today / Weekly / Monthly / Billable /
 * Non-Productive / Leave / Remaining / Efficiency) is derived here directly
 * from the Timesheet Entries. Nothing is stored or duplicated. Approval status
 * NEVER affects these numbers.
 *
 * Category rules (mirror app/core/non_productive_categories.py on the backend):
 *   - Leave        : work_category === 'non_productive' AND (leave_count > 0
 *                    OR non_productive_category === 'leave')
 *   - Non-Productive: work_category === 'non_productive' AND NOT leave
 *   - Productive   : work_category === 'productive'
 *   - Billable     : is_billable === true (any category)
 * ============================================================================
 */

export interface TimesheetEntryLike {
  entry_date?: string;
  hours: number;
  is_billable: boolean;
  work_category: string;
  leave_count?: number | null;
  non_productive_category?: string | null;
}

export function isLeaveEntry(entry: TimesheetEntryLike): boolean {
  return (
    entry.work_category === 'non_productive' &&
    ((entry.leave_count ?? 0) > 0 || entry.non_productive_category === 'leave')
  );
}

export interface TimesheetBreakdown {
  /** All hours across productive + non-productive (excludes leave). */
  workedHours: number;
  productiveHours: number;
  nonProductiveHours: number;
  billableHours: number;
  nonBillableHours: number;
  leaveDays: number;
  leaveEntries: number;
}

/** Categorize a set of entries into the canonical hour buckets. */
export function categorizeEntries(entries: TimesheetEntryLike[]): TimesheetBreakdown {
  let productiveHours = 0;
  let nonProductiveHours = 0;
  let billableHours = 0;
  let nonBillableHours = 0;
  let leaveDays = 0;
  let leaveEntries = 0;

  for (const entry of entries) {
    const hours = Number(entry.hours);
    const safeHours = Number.isFinite(hours) ? hours : 0;

    if (isLeaveEntry(entry)) {
      leaveEntries += 1;
      leaveDays += entry.leave_count && entry.leave_count > 0 ? entry.leave_count : 1;
      continue;
    }

    if (entry.work_category === 'non_productive') {
      nonProductiveHours += safeHours;
    } else {
      productiveHours += safeHours;
    }

    if (entry.is_billable) billableHours += safeHours;
    else nonBillableHours += safeHours;
  }

  return {
    workedHours: productiveHours + nonProductiveHours,
    productiveHours,
    nonProductiveHours,
    billableHours,
    nonBillableHours,
    leaveDays,
    leaveEntries,
  };
}

/** Sum entry hours. By default leave entries are excluded. */
export function sumEntryHours(
  entries: TimesheetEntryLike[],
  options: { includeLeave?: boolean } = {},
): number {
  let total = 0;
  for (const entry of entries) {
    if (!options.includeLeave && isLeaveEntry(entry)) continue;
    const hours = Number(entry.hours);
    if (Number.isFinite(hours)) total += hours;
  }
  return total;
}

export interface TimesheetMonthSummary extends TimesheetBreakdown {
  expectedHours: number;
  /** Monthly total = worked hours (productive + non-productive), excludes leave. */
  enteredHours: number;
  remainingHours: number;
  /** Percentage of expected hours completed (0-100+, may exceed 100). */
  monthlyPercent: number | null;
  /** Percentage of expected hours still remaining (0-100). */
  remainingPercent: number | null;
  efficiencyPercent: number | null;
}

export function summarizeMonthEntries(
  entries: TimesheetEntryLike[],
  expectedHours: number,
): TimesheetMonthSummary {
  const breakdown = categorizeEntries(entries);
  const enteredHours = breakdown.workedHours;
  const remainingHours = expectedHours - enteredHours;

  return {
    ...breakdown,
    expectedHours,
    enteredHours,
    remainingHours,
    monthlyPercent:
      expectedHours > 0 ? Math.round((enteredHours / expectedHours) * 100) : null,
    remainingPercent:
      expectedHours > 0
        ? Math.max(0, Math.round((remainingHours / expectedHours) * 100))
        : null,
    efficiencyPercent:
      enteredHours > 0 ? Math.round((breakdown.billableHours / enteredHours) * 100) : null,
  };
}

export function summarizeDailyHoursFromEntries(
  entries: Array<{ entry_date: string; hours: number }>,
): Map<string, number> {
  const totals = new Map<string, number>();
  for (const entry of entries) {
    const parsed = Number(entry.hours);
    if (!Number.isFinite(parsed) || parsed <= 0) continue;
    totals.set(entry.entry_date, (totals.get(entry.entry_date) ?? 0) + parsed);
  }
  return totals;
}

/** Working days (excludes weekends + holidays) in the ISO week containing a date. */
export function weekWorkingDayCount(anchorIso: string, holidayDates: Set<string>): number {
  const start = weekStartMonday(anchorIso);
  const days: string[] = [];
  for (let offset = 0; offset < 7; offset += 1) {
    const date = new Date(`${start}T12:00:00`);
    date.setDate(date.getDate() + offset);
    days.push(formatLocalIso(date));
  }
  return countWorkingDays(days, holidayDates);
}

export const GRID_COLUMNS = [
  'entryDate',
  'day',
  'toolNumber',
  'customer',
  'task',
  'billable',
  'hours',
  'notes',
] as const;

export type GridColumnKey = (typeof GRID_COLUMNS)[number];

export function nextGridCell(
  rowIndex: number,
  columnIndex: number,
  rowCount: number,
): { row: number; col: number } {
  const col = columnIndex + 1;
  if (col >= GRID_COLUMNS.length) {
    return { row: Math.min(rowIndex + 1, rowCount - 1), col: 2 };
  }
  return { row: rowIndex, col };
}

export function parseClipboardRows(text: string): string[][] {
  return text
    .trim()
    .split(/\r?\n/)
    .map((line) => line.split('\t').map((cell) => cell.trim()));
}
