import type { CurrentUser } from '../types/Auth';
import { MODULE_PERFORMANCE } from '../config/accessControl';
import { ROLES, hasRole } from './permissions';
import type { PerformanceReview } from '../types/PerformanceReview';

export type PerformanceReviewFormMode = 'create' | 'edit' | 'view';

export const PERFORMANCE_MODULE_ACTIONS = {
  view: 'view',
  create: 'create',
  edit: 'edit',
  delete: 'delete',
  approve: 'approve',
  export: 'export',
  import: 'import',
  configure: 'configure',
  edit_reviews: 'edit_reviews',
  manage_templates: 'manage_templates',
  calibrate: 'calibrate',
  open_cycles: 'open_cycles',
} as const;

export function performanceModuleActions(user: CurrentUser | null | undefined): string[] {
  if (!user?.module_actions?.[MODULE_PERFORMANCE]) {
    if (hasRole(user?.role_name ?? '', ROLES.ADMIN)) {
      return Object.values(PERFORMANCE_MODULE_ACTIONS);
    }
    return [PERFORMANCE_MODULE_ACTIONS.view];
  }
  return user.module_actions[MODULE_PERFORMANCE] ?? [];
}

export function hasPerformanceModuleAction(
  user: CurrentUser | null | undefined,
  action: string,
): boolean {
  if (!user) return false;
  if (hasRole(user.role_name, ROLES.ADMIN)) return true;
  return performanceModuleActions(user).includes(action);
}

export function canCreatePerformanceReview(
  user: CurrentUser | null | undefined,
  hasManagedTeams: boolean,
): boolean {
  if (!user) return false;
  if (hasManagedTeams) return true;
  if (hasRole(user.role_name, ROLES.ADMIN)) return true;
  return (
    hasPerformanceModuleAction(user, PERFORMANCE_MODULE_ACTIONS.create) ||
    hasPerformanceModuleAction(user, PERFORMANCE_MODULE_ACTIONS.edit) ||
    hasPerformanceModuleAction(user, PERFORMANCE_MODULE_ACTIONS.edit_reviews)
  );
}

export function getPerformanceReviewFormMode(
  user: CurrentUser | null | undefined,
  review: PerformanceReview | null | undefined,
): PerformanceReviewFormMode {
  if (!review) return 'view';
  if (review.is_published || review.stage === 'acknowledged' || review.status === 'acknowledged') {
    return 'view';
  }
  if (review.can_edit_employee_section && review.employee_id === user?.id) {
    return 'edit';
  }
  if (review.can_edit_manager_section) {
    return 'edit';
  }
  if (review.is_editable) {
    return 'edit';
  }
  return 'view';
}

export function performanceReviewIsViewOnly(
  user: CurrentUser | null | undefined,
  review: PerformanceReview,
): boolean {
  return getPerformanceReviewFormMode(user, review) === 'view';
}

export type PerformanceReviewFieldKey =
  | 'employee_summary'
  | 'manager_summary'
  | 'career_goals'
  | 'strengths_summary'
  | 'improvement_summary'
  | 'review_date'
  | 'period_label'
  | 'due_date'
  | 'total_experience'
  | 'industry_experience'
  | 'sections'
  | 'projects';

export function canEditPerformanceReviewField(
  user: CurrentUser | null | undefined,
  review: PerformanceReview,
  field: PerformanceReviewFieldKey,
): boolean {
  if (performanceReviewIsViewOnly(user, review)) {
    return false;
  }
  const canEmployee = Boolean(review.can_edit_employee_section);
  const canManager = Boolean(review.can_edit_manager_section);
  const isEmployee = review.employee_id === user?.id;

  switch (field) {
    case 'employee_summary':
      return canEmployee && isEmployee;
    case 'manager_summary':
    case 'strengths_summary':
    case 'improvement_summary':
    case 'review_date':
    case 'period_label':
    case 'due_date':
    case 'total_experience':
    case 'industry_experience':
      return canManager;
    case 'career_goals':
      return canEmployee || canManager;
    case 'sections':
    case 'projects':
      return canEmployee || canManager;
    default:
      return false;
  }
}

export function canEditSectionEmployeeNotes(
  user: CurrentUser | null | undefined,
  review: PerformanceReview,
): boolean {
  if (performanceReviewIsViewOnly(user, review)) return false;
  return Boolean(review.can_edit_employee_section) && review.employee_id === user?.id;
}

export function canEditSectionReviewerNotes(
  user: CurrentUser | null | undefined,
  review: PerformanceReview,
): boolean {
  if (performanceReviewIsViewOnly(user, review)) return false;
  return Boolean(review.can_edit_manager_section);
}

export function buildPerformanceReviewSaveBody(
  user: CurrentUser | null | undefined,
  review: PerformanceReview,
  editor: {
    period_label: string;
    review_date: string;
    due_date: string;
    total_experience: string;
    industry_experience: string;
    employee_summary: string;
    manager_summary: string;
    strengths_summary: string;
    improvement_summary: string;
    career_goals: string;
    sections: PerformanceReview['sections'];
    projects: PerformanceReview['projects'];
  },
  options?: { status?: string },
): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (canEditPerformanceReviewField(user, review, 'period_label')) {
    body.period_label = editor.period_label;
  }
  if (canEditPerformanceReviewField(user, review, 'review_date')) {
    body.review_date = editor.review_date || null;
  }
  if (canEditPerformanceReviewField(user, review, 'due_date')) {
    body.due_date = editor.due_date || null;
  }
  if (canEditPerformanceReviewField(user, review, 'total_experience')) {
    body.total_experience = editor.total_experience || null;
  }
  if (canEditPerformanceReviewField(user, review, 'industry_experience')) {
    body.industry_experience = editor.industry_experience || null;
  }
  if (canEditPerformanceReviewField(user, review, 'employee_summary')) {
    body.employee_summary = editor.employee_summary || null;
  }
  if (canEditPerformanceReviewField(user, review, 'manager_summary')) {
    body.manager_summary = editor.manager_summary || null;
  }
  if (canEditPerformanceReviewField(user, review, 'strengths_summary')) {
    body.strengths_summary = editor.strengths_summary || null;
  }
  if (canEditPerformanceReviewField(user, review, 'improvement_summary')) {
    body.improvement_summary = editor.improvement_summary || null;
  }
  if (canEditPerformanceReviewField(user, review, 'career_goals')) {
    body.career_goals = editor.career_goals || null;
  }
  if (canEditPerformanceReviewField(user, review, 'sections')) {
    body.sections = editor.sections;
  }
  if (canEditPerformanceReviewField(user, review, 'projects')) {
    body.projects = editor.projects;
  }
  if (options?.status && canEditPerformanceReviewField(user, review, 'manager_summary')) {
    body.status = options.status;
  }
  return body;
}
