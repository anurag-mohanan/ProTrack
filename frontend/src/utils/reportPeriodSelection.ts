/** Period selection helpers — map Year/Month/Week/Quarter dropdowns to API anchor dates. */

export type ReportPeriodType = 'weekly' | 'monthly' | 'quarterly' | 'yearly' | string;

const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
] as const;

export function toIsoDate(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
}

export function parseIsoDate(value: string): Date {
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return new Date();
  }
  return parsed;
}

export function mondayOf(value: Date): Date {
  const day = value.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  const monday = new Date(value);
  monday.setDate(value.getDate() + diff);
  monday.setHours(0, 0, 0, 0);
  return monday;
}

export function availableYears(spanBack = 6, spanForward = 1): number[] {
  const current = new Date().getFullYear();
  const years: number[] = [];
  for (let year = current + spanForward; year >= current - spanBack; year -= 1) {
    years.push(year);
  }
  return years;
}

export function monthOptions(): { value: number; label: string }[] {
  return MONTH_NAMES.map((label, index) => ({ value: index + 1, label }));
}

export function quarterOptions(): { value: number; label: string }[] {
  return [
    { value: 1, label: 'Q1 (Jan–Mar)' },
    { value: 2, label: 'Q2 (Apr–Jun)' },
    { value: 3, label: 'Q3 (Jul–Sep)' },
    { value: 4, label: 'Q4 (Oct–Dec)' },
  ];
}

export interface WeekOption {
  monday: string;
  weekNumber: number;
  label: string;
}

/** ISO weeks that overlap the given calendar month. */
export function weeksInMonth(year: number, month: number): WeekOption[] {
  const first = new Date(year, month - 1, 1);
  const last = new Date(year, month, 0);
  const options: WeekOption[] = [];
  const cursor = mondayOf(first);

  for (let i = 0; i < 6; i += 1) {
    const sunday = new Date(cursor);
    sunday.setDate(cursor.getDate() + 6);
    if (cursor <= last && sunday >= first) {
      const weekNumber = isoWeekNumber(cursor);
      const fmt = (d: Date) =>
        d.toLocaleDateString(undefined, { day: '2-digit', month: 'short' });
      options.push({
        monday: toIsoDate(cursor),
        weekNumber,
        label: `Week ${weekNumber} (${fmt(cursor)} – ${fmt(sunday)})`,
      });
    }
    cursor.setDate(cursor.getDate() + 7);
    if (cursor > last) {
      break;
    }
  }
  return options;
}

export function isoWeekNumber(value: Date): number {
  const date = new Date(Date.UTC(value.getFullYear(), value.getMonth(), value.getDate()));
  const dayNum = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

export function quarterFromMonth(month: number): number {
  return Math.floor((month - 1) / 3) + 1;
}

export function firstDayOfQuarter(year: number, quarter: number): string {
  const startMonth = (quarter - 1) * 3 + 1;
  return `${year}-${String(startMonth).padStart(2, '0')}-01`;
}

export function firstDayOfMonth(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}-01`;
}

export function firstDayOfYear(year: number): string {
  return `${year}-01-01`;
}

/** Normalize any date into the canonical API anchor for a period type. */
export function normalizeAnchor(periodType: ReportPeriodType, isoDate: string): string {
  const date = parseIsoDate(isoDate);
  if (periodType === 'weekly') {
    return toIsoDate(mondayOf(date));
  }
  if (periodType === 'monthly') {
    return firstDayOfMonth(date.getFullYear(), date.getMonth() + 1);
  }
  if (periodType === 'quarterly') {
    return firstDayOfQuarter(date.getFullYear(), quarterFromMonth(date.getMonth() + 1));
  }
  if (periodType === 'yearly') {
    return firstDayOfYear(date.getFullYear());
  }
  return toIsoDate(date);
}

export function defaultAnchorForPeriod(periodType: ReportPeriodType, from = new Date()): string {
  return normalizeAnchor(periodType, toIsoDate(from));
}

export function selectionFromAnchor(
  periodType: ReportPeriodType,
  anchor: string,
): {
  year: number;
  month: number;
  quarter: number;
  weekMonday: string;
} {
  const date = parseIsoDate(normalizeAnchor(periodType, anchor));
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  return {
    year,
    month,
    quarter: quarterFromMonth(month),
    weekMonday: toIsoDate(mondayOf(date)),
  };
}

export interface PeriodDateBounds {
  start: string;
  end: string;
  days: string[];
  label: string;
  /** YYYY-MM of the period start — used for calendar lock / month jump. */
  monthValue: string;
}

/** Inclusive calendar bounds for week / month / quarter / year. */
export function periodDateBounds(
  periodType: ReportPeriodType,
  anchor: string,
): PeriodDateBounds {
  const normalized = normalizeAnchor(periodType, anchor);
  const startDate = parseIsoDate(normalized);
  let endDate = new Date(startDate);

  if (periodType === 'weekly') {
    endDate.setDate(startDate.getDate() + 6);
  } else if (periodType === 'monthly') {
    endDate = new Date(startDate.getFullYear(), startDate.getMonth() + 1, 0);
  } else if (periodType === 'quarterly') {
    endDate = new Date(startDate.getFullYear(), startDate.getMonth() + 3, 0);
  } else if (periodType === 'yearly') {
    endDate = new Date(startDate.getFullYear(), 11, 31);
  }

  const start = toIsoDate(startDate);
  const end = toIsoDate(endDate);
  const days: string[] = [];
  const cursor = new Date(startDate);
  while (cursor <= endDate) {
    days.push(toIsoDate(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }

  const fmt = (iso: string) =>
    parseIsoDate(iso).toLocaleDateString(undefined, {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  const typeLabel =
    periodType === 'weekly'
      ? 'Week'
      : periodType === 'quarterly'
        ? 'Quarter'
        : periodType === 'yearly'
          ? 'Year'
          : 'Month';

  return {
    start,
    end,
    days,
    label: `${typeLabel}: ${fmt(start)} – ${fmt(end)}`,
    monthValue: `${startDate.getFullYear()}-${String(startDate.getMonth() + 1).padStart(2, '0')}`,
  };
}

export function shiftPeriodAnchor(
  periodType: ReportPeriodType,
  anchor: string,
  delta: number,
): string {
  const normalized = normalizeAnchor(periodType, anchor);
  const date = parseIsoDate(normalized);
  if (periodType === 'weekly') {
    date.setDate(date.getDate() + delta * 7);
  } else if (periodType === 'monthly') {
    date.setMonth(date.getMonth() + delta);
  } else if (periodType === 'quarterly') {
    date.setMonth(date.getMonth() + delta * 3);
  } else if (periodType === 'yearly') {
    date.setFullYear(date.getFullYear() + delta);
  }
  return normalizeAnchor(periodType, toIsoDate(date));
}

export const TIMESHEET_PERIOD_OPTIONS: { value: ReportPeriodType; label: string }[] = [
  { value: 'weekly', label: 'Week' },
  { value: 'monthly', label: 'Month' },
  { value: 'quarterly', label: 'Quarter' },
  { value: 'yearly', label: 'Year' },
];
