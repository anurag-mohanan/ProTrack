import type { Prediction, ScenarioOutcome } from '../../types/Predictive';
import { formatDate, formatNumber } from '../../utils/format';

export const FORECAST_CAVEAT =
  'Forecasts are estimates from comparable completed work. They are not commitments, actuals or approved figures.';

export function hoursText(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return `${formatNumber(value, 1)} h`;
}

export function amountText(value: string | number | null | undefined, currency?: string | null): string {
  if (value === null || value === undefined || value === '') return '—';
  return `${formatNumber(value, 2)}${currency ? ` ${currency}` : ''}`;
}

export function dateText(value: string | null | undefined): string {
  return value ? formatDate(value) : '—';
}

export function daysVariance(value: string | null | undefined): string {
  if (value === null || value === undefined) return '—';
  const days = Math.round(Number(value));
  if (days === 0) return 'On target';
  return days > 0 ? `${days} days late` : `${-days} days early`;
}

export function hoursVariance(value: string | null | undefined): string {
  if (value === null || value === undefined) return '—';
  const n = Number(value);
  if (n === 0) return 'On estimate';
  return `${n > 0 ? '+' : '−'}${formatNumber(Math.abs(n), 1)} h`;
}

export function percentOver(variance: string | null, baseline: string | null): string | null {
  const base = Number(baseline);
  if (variance === null || !baseline || !base) return null;
  return `${formatNumber((Number(variance) / base) * 100, 0)}%`;
}

type Ranged = Pick<Prediction | ScenarioOutcome, 'lower_date' | 'upper_date' | 'lower_value' | 'upper_value'>;

export function rangeText(p: Ranged, unit: 'date' | 'hours' | 'amount' = 'date'): string | null {
  if (p.lower_date && p.upper_date) return `${dateText(p.lower_date)} – ${dateText(p.upper_date)}`;
  if (p.lower_value !== null && p.upper_value !== null && p.lower_value !== undefined) {
    return unit === 'hours'
      ? `${hoursText(p.lower_value)} – ${hoursText(p.upper_value)}`
      : `${formatNumber(p.lower_value, 2)} – ${formatNumber(p.upper_value ?? 0, 2)}`;
  }
  return null;
}

export function shareText(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return `${formatNumber(Number(value) * 100, 0)}%`;
}

export function dataString(data: Record<string, unknown>, key: string): string | null {
  const value = data[key];
  return value === null || value === undefined ? null : String(value);
}

export function dataFlag(data: Record<string, unknown>, key: string): boolean {
  return data[key] === true;
}
