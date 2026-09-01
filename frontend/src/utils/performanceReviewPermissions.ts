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
