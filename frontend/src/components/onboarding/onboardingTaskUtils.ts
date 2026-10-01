import {
  RESOLVED_ITEM_STATUSES,
  type OnboardingAttentionCode,
  type OnboardingChecklistItem,
  type OnboardingItemStatus,
  type OnboardingTaskActionCode,
} from '../../api/onboarding';
import { ticketHref } from '../tickets/ticketConstants';

export const ATTENTION_LABELS: Record<OnboardingAttentionCode, string> = {
  request_missing: 'Ticket required — not created',
  request_resolved: 'Linked ticket resolved — confirm completion',
  request_cancelled: 'Linked ticket was cancelled',
  request_needs_owner: 'Linked ticket has no owner',
  request_waiting: 'Linked ticket is waiting',
  link_broken: 'Ticket link is broken',
  legacy_grouped: 'Shared legacy ticket — needs its own ticket',
  blocked: 'Blocked',
  overdue: 'Overdue',
  unassigned: 'No named owner',
};

export type TaskAction =
  | { kind: 'complete' }
  | { kind: 'status'; status: OnboardingItemStatus }
  | { kind: 'request' }
  | { kind: 'repair' };

export interface TaskActionSubmit {
  action: TaskAction;
  reason?: string;
  notes?: string;
  override?: boolean;
  priority?: 'low' | 'normal' | 'high' | 'urgent';
  details?: string;
}

/** Server action codes → the client action that performs them. */
export const ACTION_FOR_CODE: Record<OnboardingTaskActionCode, TaskAction> = {
  start: { kind: 'status', status: 'in_progress' },
  complete: { kind: 'complete' },
  waiting: { kind: 'status', status: 'waiting' },
  block: { kind: 'status', status: 'blocked' },
  waive: { kind: 'status', status: 'waived' },
  not_required: { kind: 'status', status: 'not_required' },
  cancel: { kind: 'status', status: 'cancelled' },
  reopen: { kind: 'status', status: 'not_started' },
};

export const ACTION_CODE_LABELS: Record<OnboardingTaskActionCode, string> = {
  start: 'Start',
  complete: 'Complete',
  waiting: 'Mark waiting…',
  block: 'Mark blocked…',
  waive: 'Waive…',
  not_required: 'Mark not required…',
  cancel: 'Cancel task…',
  reopen: 'Reopen',
};

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
  return item.help_ticket_id ? ticketHref(item.help_ticket_id) : '/help-desk';
}

/** Completing needs an override when the system can't confirm the work itself. */
export function completionNeedsOverride(item: OnboardingChecklistItem): boolean {
  if (item.execution_type === 'AUTOMATED') return true;
  if (item.execution_type === 'TICKET_REQUIRED') {
    return !(item.request_status === 'resolved' || item.request_status === 'closed');
  }
  return Boolean(item.validation_rule);
}
