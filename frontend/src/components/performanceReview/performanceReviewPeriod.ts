/** July annual review cycle helpers (PP-HRD-FO-20). */

export function currentReviewYear(asOf = new Date()): number {
  return asOf.getMonth() + 1 >= 7 ? asOf.getFullYear() : asOf.getFullYear();
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
