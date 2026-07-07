export type HoursPerformanceTone = 'success' | 'warning' | 'error';

/** Green = under/at quoted; amber = up to 10% over; red = beyond 10% over quoted. */
export function hoursPerformanceTone(actual: number, quoted: number): HoursPerformanceTone {
  if (quoted <= 0) return 'success';
  const variance = actual - quoted;
  if (variance <= 0) return 'success';
  const pctOver = (variance / quoted) * 100;
  if (pctOver <= 10) return 'warning';
  return 'error';
}

export function hoursVariance(actual: number, quoted: number): number {
  return actual - quoted;
}

export function hoursUtilizationPercent(actual: number, quoted: number): number {
  if (quoted <= 0) return 0;
  return Math.min(100, Math.max(0, (actual / quoted) * 100));
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
