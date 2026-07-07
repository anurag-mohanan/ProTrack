import { formatNumber } from './format';

export type HoursPerformanceTone = 'success' | 'warning' | 'error';

/** Green = under/at quoted; amber = up to 10% over; red = beyond 10% over quoted. */
export function hoursPerformanceTone(actual: number, quoted: number): HoursPerformanceTone {
  return hoursUtilizationTone(actual, quoted);
}

export function hoursVariance(actual: number, quoted: number): number {
  return actual - quoted;
}

export function hoursUtilizationPercent(actual: number, quoted: number): number {
  if (quoted <= 0) return 0;
  return Math.min(100, Math.max(0, (actual / quoted) * 100));
}

/** Burn rate vs quoted — may exceed 100% when over budget. */
export function hoursBurnPercent(actual: number, quoted: number): number {
  if (quoted <= 0) return 0;
  return Math.max(0, (actual / quoted) * 100);
}

/**
 * Green = within quoted and under 90% used.
 * Amber = 90–100% of quoted (still at or under).
 * Red = over quoted.
 */
export function hoursUtilizationTone(actual: number, quoted: number): HoursPerformanceTone {
  if (quoted <= 0) return 'success';
  if (actual > quoted) return 'error';
  const pct = hoursBurnPercent(actual, quoted);
  if (pct >= 90) return 'warning';
  return 'success';
}

export function formatHoursOverPercent(actual: number, quoted: number): string | null {
  if (quoted <= 0 || actual <= quoted) return null;
  const overPct = ((actual - quoted) / quoted) * 100;
  return `${formatNumber(Math.round(overPct), 0)}% Over`;
}

/** Estimated hours at completion from milestone progress and actual burn. */
export function calculateEAC(actual: number, progressPercent: number): number | null {
  if (progressPercent <= 0 || actual <= 0) return null;
  return actual / (progressPercent / 100);
}

export function forecastVariance(
  actual: number,
  quoted: number,
  progressPercent: number,
): number | null {
  const eac = calculateEAC(actual, progressPercent);
  if (eac == null) return null;
  return eac - quoted;
}

export function formatHoursVariance(variance: number, decimals = 0): string {
  const rounded = Number(variance.toFixed(decimals));
  if (rounded === 0) return '0';
  return `${rounded > 0 ? '+' : ''}${rounded}`;
}
