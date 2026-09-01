import { currentReviewYear, formatReviewPeriod } from '../components/performanceReview/performanceReviewPeriod';
import type { FormStatusCategory, PerformanceReview } from '../types/PerformanceReview';

export type StatusQuickFilter = 'all' | FormStatusCategory;

export function reviewYearFromReview(review: PerformanceReview): number {
  if (review.review_period_end) {
    const end = new Date(`${review.review_period_end}T00:00:00`);
    if (!Number.isNaN(end.getTime())) return end.getFullYear();
  }
  if (review.review_period_start) {
    const start = new Date(`${review.review_period_start}T00:00:00`);
    if (!Number.isNaN(start.getTime())) return start.getFullYear();
  }
  const match = review.period_label.match(/(\d{4})/g);
  if (match?.length) return Number(match[match.length - 1]);
  return currentReviewYear();
}

export function getReviewDisplayStatus(review: PerformanceReview): {
  label: string;
  category: FormStatusCategory;
  editable: boolean;
} {
  const editable = Boolean(
    review.is_editable &&
      !review.is_published &&
      (review.can_edit_employee_section || review.can_edit_manager_section || review.is_editable),
  );
  if (review.is_published || review.stage === 'acknowledged' || review.status === 'acknowledged') {
    return { label: 'Completed', category: 'completed', editable: false };
  }
  if (review.due_date) {
    const due = new Date(`${review.due_date}T00:00:00`);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (due < today && review.status === 'draft' && review.stage === 'self') {
      return { label: 'Overdue', category: 'overdue', editable };
    }
  }
  if (review.stage === 'self') {
    if (review.can_edit_employee_section || review.can_submit_self) {
      return {
        label: review.can_submit_self ? 'Self review in progress' : 'In progress',
        category: 'in_progress',
        editable,
      };
    }
    if (review.can_edit_manager_section) {
      return { label: 'Awaiting employee', category: 'pending_review', editable };
    }
    return {
      label: 'Not started',
      category: 'not_started',
      editable,
    };
  }
  if (review.stage === 'manager') {
    return { label: 'Manager review', category: 'pending_review', editable };
  }
  if (review.stage === 'calibration') {
    return { label: 'Calibration', category: 'pending_review', editable };
  }
  if (review.stage === 'final') {
    return { label: 'Pending finalization', category: 'pending_review', editable };
  }
  if (review.status === 'submitted') {
    return { label: 'Submitted', category: 'pending_review', editable };
  }
  return { label: 'In progress', category: 'in_progress', editable };
}

export function reviewNeedsUserAction(review: PerformanceReview, userId?: string | null): boolean {
  if (!userId) return false;
  if (review.can_submit_self && review.employee_id === userId) return true;
  if (review.can_submit_manager || review.can_calibrate) return true;
  if (review.can_acknowledge && review.employee_id === userId) return true;
  return false;
}

export function reviewActionLabel(review: PerformanceReview, userId?: string | null): string {
  const display = getReviewDisplayStatus(review);
  if (display.category === 'completed') return 'View review';
  if (review.can_acknowledge && review.employee_id === userId) return 'Acknowledge';
  if (review.can_submit_self && review.employee_id === userId) return 'Continue self-review';
  if (review.can_submit_manager) return 'Continue manager review';
  if (review.can_calibrate) return 'Review & calibrate';
  if (display.editable) return 'Open review';
  return 'View review';
}

export function countRatedItems(review: PerformanceReview): { rated: number; total: number } {
  let rated = 0;
  let total = 0;
  for (const section of review.sections) {
    for (const item of section.items) {
      total += 1;
      if (item.rating !== null && item.rating !== undefined && item.rating !== '') {
        rated += 1;
      }
    }
  }
  return { rated, total };
}

export function filterReviews(
  reviews: PerformanceReview[],
  filters: {
    year: number | 'all';
    status: StatusQuickFilter;
    teamId: string;
    department: string;
    search: string;
    needsActionOnly: boolean;
    userId?: string | null;
    kind?: 'annual' | 'quarterly' | null;
  },
): PerformanceReview[] {
  const search = filters.search.trim().toLowerCase();
  return reviews.filter((review) => {
    if (filters.kind && (review.cycle_kind || 'annual') !== filters.kind) return false;
    if (filters.year !== 'all' && reviewYearFromReview(review) !== filters.year) return false;
    const display = getReviewDisplayStatus(review);
    if (filters.status !== 'all' && display.category !== filters.status) return false;
    if (filters.teamId && review.team_id !== filters.teamId) return false;
    if (
      filters.department &&
      (review.employee_department ?? '').toLowerCase() !== filters.department.toLowerCase()
    ) {
      return false;
    }
    if (filters.needsActionOnly && !reviewNeedsUserAction(review, filters.userId)) return false;
    if (search) {
      const haystack = [
        review.employee_name,
        review.team_name,
        review.employee_department,
        review.period_label,
        review.employee_designation,
        String(reviewYearFromReview(review)),
        display.label,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
}

export type YearGroup = {
  year: number;
  reviews: PerformanceReview[];
  completed: number;
  inProgress: number;
  pending: number;
  overdue: number;
};

export function groupReviewsByYear(reviews: PerformanceReview[]): YearGroup[] {
  const map = new Map<number, PerformanceReview[]>();
  for (const review of reviews) {
    const year = reviewYearFromReview(review);
    const bucket = map.get(year) ?? [];
    bucket.push(review);
    map.set(year, bucket);
  }
  return Array.from(map.entries())
    .sort((a, b) => b[0] - a[0])
    .map(([year, rows]) => {
      let completed = 0;
      let inProgress = 0;
      let pending = 0;
      let overdue = 0;
      for (const row of rows) {
        const display = getReviewDisplayStatus(row);
        if (display.category === 'completed') completed += 1;
        else if (display.category === 'overdue') overdue += 1;
        else if (display.category === 'pending_review') pending += 1;
        else inProgress += 1;
      }
      return { year, reviews: rows, completed, inProgress, pending, overdue };
    });
}

export function reviewPeriodLabel(review: PerformanceReview): string {
  return formatReviewPeriod(review.review_period_start, review.review_period_end);
}

export function availableReviewYears(reviews: PerformanceReview[]): number[] {
  const years = new Set<number>();
  for (const review of reviews) years.add(reviewYearFromReview(review));
  const current = currentReviewYear();
  years.add(current);
  return Array.from(years).sort((a, b) => b - a);
}

export function availableDepartments(reviews: PerformanceReview[]): string[] {
  const set = new Set<string>();
  for (const review of reviews) {
    if (review.employee_department) set.add(review.employee_department);
  }
  return Array.from(set).sort();
}
