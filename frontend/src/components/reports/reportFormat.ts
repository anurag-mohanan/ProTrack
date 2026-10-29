import type { PerformancePeriodType } from '../../types/EngineeringPerformance';
import { formatNumber } from '../../utils/format';

type Numeric = number | string | null | undefined;

export const PERIOD_OPTIONS: { value: PerformancePeriodType; label: string }[] = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly (financial)' },
  { value: 'yearly', label: 'Financial year' },
  { value: 'custom', label: 'Custom range' },
];

export const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function fyStartYearFor(date: Date, fyStartMonth: number): number {
  return date.getMonth() + 1 >= fyStartMonth ? date.getFullYear() : date.getFullYear() - 1;
}

export function fyLabel(startYear: number, fyStartMonth: number): string {
  if (fyStartMonth === 1) return `FY ${startYear}`;
  return `FY ${startYear}-${String((startYear + 1) % 100).padStart(2, '0')}`;
}

/** First day of financial quarter `quarter` (1–4) of the FY starting in `startYear`. */
export function fyQuarterStart(startYear: number, quarter: number, fyStartMonth: number): Date {
  const offset = fyStartMonth - 1 + (quarter - 1) * 3;
  return new Date(startYear + Math.floor(offset / 12), offset % 12, 1);
}

export function fyQuarterLabel(quarter: number, fyStartMonth: number): string {
  const first = (fyStartMonth - 1 + (quarter - 1) * 3) % 12;
  const last = (first + 2) % 12;
  return `Q${quarter} (${MONTH_SHORT[first]}–${MONTH_SHORT[last]})`;
}

export function fyQuarterFor(date: Date, fyStartMonth: number): number {
  const monthsIn = (date.getMonth() + 1 - fyStartMonth + 12) % 12;
  return Math.floor(monthsIn / 3) + 1;
}

function isBlank(value: Numeric): value is null | undefined | '' {
  return value === null || value === undefined || value === '';
}

export function hours(value: Numeric): string {
  return isBlank(value) ? '—' : formatNumber(value, 1);
}

export function percent(value: Numeric): string {
  return isBlank(value) ? '—' : `${formatNumber(value, 1)}%`;
}

export function signedHours(value: Numeric): string {
  if (isBlank(value)) return '—';
  const numeric = Number(value);
  return `${numeric > 0 ? '+' : ''}${formatNumber(numeric, 1)}`;
}

export function signedDays(value: Numeric): string {
  if (isBlank(value)) return '—';
  const numeric = Number(value);
  return `${numeric > 0 ? '+' : ''}${formatNumber(numeric, numeric % 1 === 0 ? 0 : 1)} d`;
}

export function varianceColor(value: Numeric): string | undefined {
  if (isBlank(value) || Number(value) === 0) return undefined;
  return Number(value) > 0 ? 'error.main' : 'success.main';
}
