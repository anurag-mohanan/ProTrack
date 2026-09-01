/** July annual review cycle helpers (PP-HRD-FO-20). */

export function currentReviewYear(asOf = new Date()): number {
  return asOf.getMonth() + 1 >= 7 ? asOf.getFullYear() + 1 : asOf.getFullYear();
}

export function defaultPeriodLabel(reviewYear = currentReviewYear()): string {
  return `FY ${reviewYear - 1}-${String(reviewYear).slice(-2)}`;
}

export function reviewPeriodBounds(reviewYear = currentReviewYear()): { start: string; end: string } {
  return {
    start: `${reviewYear - 1}-07-01`,
    end: `${reviewYear}-06-30`,
  };
}

export function formatReviewPeriod(start?: string | null, end?: string | null): string {
  if (!start || !end) return 'July–June review year';
  return `${start} → ${end}`;
}

/** Format tenure from an ISO date string (yyyy-mm-dd) to e.g. "2y 3m". */
export function formatTenureFromDate(start?: string | null, asOf = new Date()): string {
  if (!start) return '';
  const parsed = new Date(`${start}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return '';
  let months =
    (asOf.getFullYear() - parsed.getFullYear()) * 12 + (asOf.getMonth() - parsed.getMonth());
  if (asOf.getDate() < parsed.getDate()) months -= 1;
  if (months < 0) months = 0;
  const years = Math.floor(months / 12);
  const rem = months % 12;
  if (years && rem) return `${years}y ${rem}m`;
  if (years) return `${years} year${years === 1 ? '' : 's'}`;
  return `${rem} month${rem === 1 ? '' : 's'}`;
}
