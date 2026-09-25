import {
  RESOLVED_ITEM_STATUSES,
  type OnboardingAttentionCode,
  type OnboardingChecklistItem,
  type OnboardingItemStatus,
} from '../../api/onboarding';

export const ATTENTION_LABELS: Record<OnboardingAttentionCode, string> = {
  request_missing: 'Request not created',
  request_resolved: 'Linked request resolved — confirm completion',
  request_cancelled: 'Linked request was cancelled',
  blocked: 'Blocked',
  overdue: 'Overdue',
  unassigned: 'No named owner',
};

export type TaskAction =
  | { kind: 'complete' }
  | { kind: 'status'; status: OnboardingItemStatus }
  | { kind: 'request' };

export interface TaskActionSubmit {
  action: TaskAction;
  reason?: string;
  notes?: string;
  override?: boolean;
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  details?: string;
}

export function isResolved(status: OnboardingItemStatus) {
  return RESOLVED_ITEM_STATUSES.has(status);
}

export function sectionProgress(items: OnboardingChecklistItem[]) {
  const resolved = items.filter((item) => isResolved(item.status)).length;
  return { resolved, total: items.length };
}

export function actionableAttention(item: OnboardingChecklistItem) {
  return item.attention.filter((code) => code !== 'unassigned');
}

export function requestHref(item: OnboardingChecklistItem) {
  return item.help_ticket_id ? `/help-desk?ticket=${item.help_ticket_id}` : '/help-desk';
}
