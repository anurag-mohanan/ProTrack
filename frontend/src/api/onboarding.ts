import { apiClient } from './client';

export type OnboardingItemStatus = 'pending' | 'completed' | 'not_applicable';
export type OnboardingChecklistStatus = 'in_progress' | 'completed' | 'cancelled';

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
  completed_by_id: string | null;
  completed_by_name: string | null;
  completion_date: string | null;
  notes: string | null;
  can_edit: boolean;
  is_mine: boolean;
  created_at: string;
  updated_at: string;
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
  pending_items: number;
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
    payload: {
      status: OnboardingItemStatus;
      completion_date?: string | null;
      notes?: string | null;
    },
  ): Promise<OnboardingChecklistDetail> => {
    const { data } = await apiClient.post<OnboardingChecklistDetail>(
      `/hr/onboarding/${checklistId}/items/${itemId}/status`,
      payload,
    );
    return data;
  },
};
