import { apiClient } from './client';

export type CompensationChangeRequest = {
  id: string;
  user_id: string;
  employee_name?: string | null;
  request_type: 'hike' | 'promotion';
  stage: 'suggested' | 'l1_approved' | 'l2_approved' | 'applied' | 'rejected';
  status: string;
  suggested_by_id?: string | null;
  suggested_by_name?: string | null;
  hike_pct?: number | string | null;
  currency_code: string;
  current_monthly_salary?: number | string | null;
  proposed_monthly_salary?: number | string | null;
  new_role_id?: string | null;
  new_role_name?: string | null;
  new_designation?: string | null;
  new_working_model_id?: string | null;
  new_working_model_name?: string | null;
  effective_date: string;
  justification?: string | null;
  l1_approver_id?: string | null;
  l1_approver_name?: string | null;
  l1_at?: string | null;
  l2_approver_id?: string | null;
  l2_approver_name?: string | null;
  l2_at?: string | null;
  applied_at?: string | null;
  rejection_reason?: string | null;
  created_at?: string | null;
  can_approve_l1: boolean;
  can_approve_l2: boolean;
  can_withdraw: boolean;
};

export type CompensationChangeCreate = {
  user_id: string;
  request_type: 'hike' | 'promotion';
  hike_pct?: number | null;
  effective_date: string;
  justification?: string | null;
  new_role_id?: string | null;
  new_designation?: string | null;
  new_working_model_id?: string | null;
};

export type CompensationWorkflowAction = {
  action: 'approve-l1' | 'approve-l2' | 'reject' | 'withdraw';
  rejection_reason?: string | null;
};

export async function fetchCompensationRequests(params?: {
  stage?: string;
  user_id?: string;
}): Promise<CompensationChangeRequest[]> {
  const query = new URLSearchParams();
  if (params?.stage) query.set('stage', params.stage);
  if (params?.user_id) query.set('user_id', params.user_id);
  const qs = query.toString();
  return (
    await apiClient.get<CompensationChangeRequest[]>(
      `/hr/performance/comp-requests${qs ? `?${qs}` : ''}`,
    )
  ).data;
}

export async function createCompensationRequest(
  payload: CompensationChangeCreate,
): Promise<CompensationChangeRequest> {
  return (
    await apiClient.post<CompensationChangeRequest>('/hr/performance/comp-requests', payload)
  ).data;
}

export async function actOnCompensationRequest(
  id: string,
  payload: CompensationWorkflowAction,
): Promise<CompensationChangeRequest> {
  return (
    await apiClient.post<CompensationChangeRequest>(
      `/hr/performance/comp-requests/${id}/workflow`,
      payload,
    )
  ).data;
}

export type UserLifecycleHistory = {
  events: {
    id: string;
    event_type: string;
    effective_date: string;
    from_value?: string | null;
    to_value?: string | null;
    applied_at?: string | null;
    created_by_name?: string | null;
    created_at?: string | null;
  }[];
  working_model_periods: {
    id: string;
    working_model_id?: string | null;
    working_model_name?: string | null;
    effective_from: string;
    effective_to?: string | null;
    notes?: string | null;
  }[];
};

export async function fetchUserLifecycle(userId: string): Promise<UserLifecycleHistory> {
  return (await apiClient.get<UserLifecycleHistory>(`/hr/users/${userId}/lifecycle`)).data;
}

export async function promoteUser(
  userId: string,
  payload: { new_role_id?: string | null; new_designation?: string | null; effective_date: string; notes?: string | null },
): Promise<void> {
  await apiClient.post(`/hr/users/${userId}/promote`, payload);
}

export async function changeUserBilling(
  userId: string,
  payload: { new_working_model_id?: string | null; effective_date: string; notes?: string | null },
): Promise<void> {
  await apiClient.post(`/hr/users/${userId}/billing-change`, payload);
}

export async function transferUser(
  userId: string,
  payload: { target_team_id: string; effective_date: string; update_reporting_manager?: boolean },
): Promise<void> {
  await apiClient.post(`/hr/users/${userId}/transfer`, payload);
}
