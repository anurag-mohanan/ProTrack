import { apiClient } from './client';

export type OnboardingItemStatus =
  | 'not_started'
  | 'in_progress'
  | 'blocked'
  | 'completed'
  | 'not_required'
  | 'waived';
export type OnboardingChecklistStatus = 'in_progress' | 'completed' | 'cancelled';

export const RESOLVED_ITEM_STATUSES: ReadonlySet<OnboardingItemStatus> = new Set([
  'completed',
  'not_required',
  'waived',
]);

export type OnboardingAttentionCode =
  | 'request_missing'
  | 'request_resolved'
  | 'request_cancelled'
  | 'blocked'
  | 'overdue'
  | 'unassigned';

export interface OnboardingChecklistItem {
  id: string;
  checklist_id: string;
  section: string;
  sort_order: number;
  item_text: string;
  responsibility: string;
  responsibility_label: string;
  status: OnboardingItemStatus;
  status_label: string;
  owner_user_id: string | null;
  owner_name: string | null;
  help_ticket_id: string | null;
  help_ticket_number: string | null;
  request_status: string | null;
  request_category: string | null;
  requires_request: boolean;
  completed_by_id: string | null;
  completed_by_name: string | null;
  completion_date: string | null;
  completed_at: string | null;
  completion_type: 'manual' | 'request' | 'manual_override' | null;
  notes: string | null;
  due_date: string | null;
  is_overdue: boolean;
  status_reason: string | null;
  status_changed_at: string | null;
  status_changed_by_name: string | null;
  validation_rule: string | null;
  attention: OnboardingAttentionCode[];
  can_edit: boolean;
  can_waive: boolean;
  can_create_request: boolean;
  is_mine: boolean;
  created_at: string;
  updated_at: string;
}

export interface OnboardingItemHistoryEvent {
  at: string | null;
  actor_name: string | null;
  event: 'created' | 'status_changed' | 'request_linked';
  old_status: string | null;
  new_status: string | null;
  reason: string | null;
  note: string | null;
  completion_type: string | null;
  ticket_number: string | null;
  source: string | null;
}

export interface OnboardingAttentionRow {
  checklist_id: string;
  item_id: string;
  employee_name: string | null;
  item_text: string;
  responsibility: string;
  status: OnboardingItemStatus;
  due_date: string | null;
  attention: OnboardingAttentionCode[];
  ticket_number: string | null;
}

export interface OnboardingAttentionSummary {
  total_tasks: number;
  actionable_total: number;
  counts: Record<OnboardingAttentionCode, number>;
  labels: Record<OnboardingAttentionCode, string>;
  items: OnboardingAttentionRow[];
}

export interface OnboardingItemStatusPayload {
  status: OnboardingItemStatus;
  completion_date?: string | null;
  notes?: string | null;
  reason?: string | null;
  override?: boolean;
}

export interface OnboardingTriggeredTicket {
  responsibility: string;
  responsibility_label: string;
  ticket_id: string;
  ticket_number: string;
  category: string;
  assignee_id: string | null;
  item_count: number;
}

export interface OnboardingChecklist {
  id: string;
  template_id: string | null;
  template_code: string | null;
  template_name: string | null;
  employee_user_id: string | null;
  employee_name: string;
  employee_code: string | null;
  joining_date: string | null;
  designation: string | null;
  department_name: string | null;
  org_department_id: string | null;
  team_id: string | null;
  team_name: string | null;
  role_id: string | null;
  role_name: string | null;
  reporting_manager_id: string | null;
  reporting_manager_name: string | null;
  status: OnboardingChecklistStatus;
  status_label: string;
  notes: string | null;
  created_by_id: string | null;
  created_by_name: string | null;
  completed_at: string | null;
  is_published: boolean;
  published_at: string | null;
  published_by_id: string | null;
  total_items: number;
  completed_items: number;
  resolved_items: number;
  pending_items: number;
  blocked_items: number;
  attention_items: number;
  overdue_items: number;
  completion_percent: number;
  can_manage: boolean;
  my_pending_items: number;
  created_at: string;
  updated_at: string;
}

export interface OnboardingChecklistDetail extends OnboardingChecklist {
  items: OnboardingChecklistItem[];
  sections: string[];
  triggered_tickets: OnboardingTriggeredTicket[];
  /** Present only when onboarding auto-created a new User account. */
  provisioned_temporary_password?: string | null;
}

export interface OnboardingChecklistCreate {
  employee_name: string;
  employee_user_id?: string | null;
  employee_email?: string | null;
  employee_code?: string | null;
  joining_date?: string | null;
  designation?: string | null;
  department_name?: string | null;
  org_department_id?: string | null;
  team_id?: string | null;
  role_id?: string | null;
  reporting_manager_id?: string | null;
  reporting_manager_name?: string | null;
  notes?: string | null;
  template_id?: string | null;
}

export interface OnboardingChecklistUpdate {
  employee_name?: string;
  employee_user_id?: string | null;
  employee_code?: string | null;
  joining_date?: string | null;
  designation?: string | null;
  department_name?: string | null;
  org_department_id?: string | null;
  team_id?: string | null;
  role_id?: string | null;
  reporting_manager_id?: string | null;
  reporting_manager_name?: string | null;
  notes?: string | null;
  status?: OnboardingChecklistStatus;
}

function buildQuery(params?: Record<string, string | undefined>) {
  if (!params) return '';
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value != null && value !== '') qs.set(key, value);
  });
  const raw = qs.toString();
  return raw ? `?${raw}` : '';
}

export const onboardingApi = {
  list: async (params?: { status?: string }): Promise<OnboardingChecklist[]> => {
    const { data } = await apiClient.get<OnboardingChecklist[]>(
      `/hr/onboarding${buildQuery(params)}`,
    );
    return data;
  },
  get: async (id: string): Promise<OnboardingChecklistDetail> => {
    const { data } = await apiClient.get<OnboardingChecklistDetail>(`/hr/onboarding/${id}`);
    return data;
  },
  create: async (payload: OnboardingChecklistCreate): Promise<OnboardingChecklistDetail> => {
    const { data } = await apiClient.post<OnboardingChecklistDetail>('/hr/onboarding', payload);
    return data;
  },
  update: async (
    id: string,
    payload: OnboardingChecklistUpdate,
  ): Promise<OnboardingChecklistDetail> => {
    const { data } = await apiClient.patch<OnboardingChecklistDetail>(
      `/hr/onboarding/${id}`,
      payload,
    );
    return data;
  },
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/hr/onboarding/${id}`);
  },
  publish: async (id: string): Promise<OnboardingChecklistDetail> => {
    const { data } = await apiClient.post<OnboardingChecklistDetail>(
      `/hr/onboarding/${id}/publish`,
    );
    return data;
  },
  setItemStatus: async (
    checklistId: string,
    itemId: string,
    payload: OnboardingItemStatusPayload,
  ): Promise<OnboardingChecklistDetail> => {
    const { data } = await apiClient.post<OnboardingChecklistDetail>(
      `/hr/onboarding/${checklistId}/items/${itemId}/status`,
      payload,
    );
    return data;
  },
  createItemRequest: async (
    checklistId: string,
    itemId: string,
    payload: { priority?: 'low' | 'medium' | 'high' | 'urgent'; details?: string | null },
  ): Promise<OnboardingChecklistDetail> => {
    const { data } = await apiClient.post<OnboardingChecklistDetail>(
      `/hr/onboarding/${checklistId}/items/${itemId}/request`,
      payload,
    );
    return data;
  },
  updateItem: async (
    checklistId: string,
    itemId: string,
    payload: { due_date?: string | null; owner_user_id?: string | null; notes?: string | null },
  ): Promise<OnboardingChecklistDetail> => {
    const { data } = await apiClient.patch<OnboardingChecklistDetail>(
      `/hr/onboarding/${checklistId}/items/${itemId}`,
      payload,
    );
    return data;
  },
  itemHistory: async (checklistId: string, itemId: string): Promise<OnboardingItemHistoryEvent[]> => {
    const { data } = await apiClient.get<OnboardingItemHistoryEvent[]>(
      `/hr/onboarding/${checklistId}/items/${itemId}/history`,
    );
    return data;
  },
  attention: async (params?: { responsibility?: string }): Promise<OnboardingAttentionSummary> => {
    const { data } = await apiClient.get<OnboardingAttentionSummary>(
      `/hr/onboarding/attention${buildQuery(params)}`,
    );
    return data;
  },
};
