import { apiClient } from './client';

export type OnboardingItemStatus =
  | 'not_started'
  | 'ready'
  | 'in_progress'
  | 'waiting'
  | 'blocked'
  | 'completed'
  | 'not_required'
  | 'waived'
  | 'cancelled';

export type OnboardingExecutionType =
  | 'CHECKLIST_ONLY'
  | 'TICKET_REQUIRED'
  | 'APPROVAL_REQUIRED'
  | 'EXTERNAL_DEPENDENCY'
  | 'OPTIONAL'
  | 'AUTOMATED';

export type OnboardingTaskActionCode =
  | 'start'
  | 'complete'
  | 'waiting'
  | 'block'
  | 'waive'
  | 'not_required'
  | 'cancel'
  | 'reopen';
export type OnboardingChecklistStatus = 'in_progress' | 'completed' | 'cancelled';

export const RESOLVED_ITEM_STATUSES: ReadonlySet<OnboardingItemStatus> = new Set([
  'completed',
  'not_required',
  'waived',
  'cancelled',
]);

export type OnboardingAttentionCode =
  | 'request_missing'
  | 'request_resolved'
  | 'request_cancelled'
  | 'request_needs_owner'
  | 'request_waiting'
  | 'link_broken'
  | 'legacy_grouped'
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
  completion_type:
    | 'manual'
    | 'request'
    | 'manual_override'
    | 'evidence'
    | 'automated'
    | 'approved'
    | null;
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
  execution_type: OnboardingExecutionType;
  execution_type_label: string;
  mandatory: boolean;
  blocks_completion: boolean;
  evidence_required: boolean;
  reversible: boolean;
  confirm_by: string | null;
  confirm_by_label: string | null;
  can_approve: boolean;
  evidence_note: string | null;
  request_status_label: string | null;
  request_assignee_name: string | null;
  request_needs_owner: boolean;
  link_broken: boolean;
  allowed_actions: OnboardingTaskActionCode[];
  can_repair_link: boolean;
  created_at: string;
  updated_at: string;
}

export interface OnboardingTemplateItemConfig {
  execution_type: OnboardingExecutionType;
  responsibility: string;
  owner_role: string | null;
  priority: 'low' | 'normal' | 'high' | 'urgent' | null;
  due_offset_days: number | null;
  evidence_required: boolean;
  confirm_by: string;
  reversible: boolean;
  mandatory: boolean;
  blocks_completion: boolean;
  ticket_category: string | null;
  ticket_subcategory: string | null;
  completion_rule: 'resolved' | 'closed';
}

export interface OnboardingTemplateItem extends OnboardingTemplateItemConfig {
  section_index: number;
  item_index: number;
  section: string;
  text: string;
  responsibility_label: string;
  execution_type_label: string;
  validation: string | null;
}

export interface OnboardingTemplateConfig {
  id: string;
  code: string;
  name: string;
  version: number;
  items: OnboardingTemplateItem[];
  execution_types: Record<string, string>;
  confirm_by: Record<string, string>;
  completion_rules: Record<string, string>;
  ticket_subcategories: Record<string, Record<string, string>>;
  responsibilities: Record<string, string>;
}

export interface OnboardingTemplateSummary {
  id: string;
  code: string;
  name: string;
  version: number;
  is_active: boolean;
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
    payload: { priority?: 'low' | 'normal' | 'high' | 'urgent'; details?: string | null },
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
  repairLink: async (
    checklistId: string,
    itemId: string,
  ): Promise<{ actions: string[]; checklist: OnboardingChecklistDetail }> => {
    const { data } = await apiClient.post<{ actions: string[]; checklist: OnboardingChecklistDetail }>(
      `/hr/onboarding/${checklistId}/items/${itemId}/repair-link`,
    );
    return data;
  },
  capabilities: async (): Promise<{ can_configure_templates: boolean }> => {
    const { data } = await apiClient.get<{ can_configure_templates: boolean }>('/hr/onboarding/capabilities');
    return data;
  },
  templates: async (): Promise<OnboardingTemplateSummary[]> => {
    const { data } = await apiClient.get<OnboardingTemplateSummary[]>('/hr/onboarding/templates');
    return data;
  },
  templateConfig: async (templateId: string): Promise<OnboardingTemplateConfig> => {
    const { data } = await apiClient.get<OnboardingTemplateConfig>(
      `/hr/onboarding/templates/${templateId}/config`,
    );
    return data;
  },
  updateTemplateItem: async (
    templateId: string,
    sectionIndex: number,
    itemIndex: number,
    payload: OnboardingTemplateItemConfig,
  ): Promise<OnboardingTemplateConfig> => {
    const { data } = await apiClient.put<OnboardingTemplateConfig>(
      `/hr/onboarding/templates/${templateId}/items/${sectionIndex}/${itemIndex}`,
      payload,
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
