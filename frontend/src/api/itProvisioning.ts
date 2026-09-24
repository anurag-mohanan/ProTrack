import { apiClient } from './client';
import type { User } from '../types';

export type ComputerTypeCode =
  | 'ENG_WS'
  | 'GENERAL_WS'
  | 'IT_WS'
  | 'ENG_LAPTOP'
  | 'GENERAL_LAPTOP';

export interface ProvisioningHardware {
  computer_required: boolean;
  computer_type?: ComputerTypeCode | string | null;
  computer_type_label?: string | null;
  computer_is_required?: boolean;
  monitor_quantity: number;
  monitor_is_required?: boolean;
  mouse_3d_required: boolean;
  mouse_3d_is_required?: boolean;
  mouse_3d_model_hint?: string | null;
  wireless_mouse_required?: boolean;
  laptop_dock_required?: boolean;
  laptop_bag_required?: boolean;
  headset_required?: boolean;
  wireless_keyboard_required?: boolean;
}

export interface ProvisioningSoftwareLine {
  id?: string;
  software_id: string;
  software_name?: string | null;
  requirement_level?: string;
  license_required?: boolean;
  version?: string | null;
  purpose?: string | null;
  priority?: string;
  status?: string;
}

export interface ProvisioningRequest {
  id: string;
  user_id: string;
  employee_name?: string | null;
  employee_code?: string | null;
  designation?: string | null;
  joining_date?: string | null;
  ticket_id?: string | null;
  ticket_number?: string | null;
  shift_id?: string | null;
  shift_display?: string | null;
  required_by?: string | null;
  priority: string;
  status: string;
  assigned_it_user_id?: string | null;
  assigned_it_user_name?: string | null;
  processing_started_at?: string | null;
  completed_at?: string | null;
  notes?: string | null;
  is_overdue?: boolean;
  hardware?: ProvisioningHardware | null;
  software?: ProvisioningSoftwareLine[];
  created_at?: string;
  updated_at?: string;
}

export interface ProvisioningDashboard {
  new_employee_requests: number;
  open_it_requests: number;
  due_today: number;
  overdue_requests: number;
  waiting_for_hardware: number;
  waiting_for_software_license: number;
  ready_for_joining: number;
  completed: number;
  hardware_demand: {
    by_computer_type?: { code: string; label: string; required: number }[];
    monitors_required?: number;
    mice_3d_required?: number;
    wireless_mice_required?: number;
  };
  software_demand: {
    software_id: string;
    software_name?: string | null;
    requested: number;
    available: number;
    assigned: number;
    shortage: number;
  }[];
}

export interface OnboardingReadiness {
  user_id: string;
  overall: string;
  items: {
    key: string;
    label: string;
    required?: boolean;
    done?: boolean;
    status?: string | null;
  }[];
  required_count: number;
  done_required_count: number;
  provisioning_request_id?: string | null;
}

export interface Employee360 {
  overview: Record<string, unknown>;
  employment: Record<string, unknown>;
  shift?: Record<string, unknown> | null;
  it_assets: Record<string, unknown>[];
  workstation_packages?: Record<string, unknown>[];
  software_licenses: Record<string, unknown>[];
  performance_reviews: Record<string, unknown>[];
  projects: Record<string, unknown>[];
  timesheets: Record<string, unknown>;
  onboarding?: OnboardingReadiness | null;
}

export interface HireWithItPayload {
  user: Record<string, unknown>;
  shift_id?: string | null;
  hardware: Partial<ProvisioningHardware>;
  software: ProvisioningSoftwareLine[];
  required_by?: string | null;
  priority?: string;
  notes?: string | null;
  create_checklist?: boolean;
}

export const itProvisioningKeys = {
  all: ['it-provisioning'] as const,
  requests: (filters?: Record<string, unknown>) =>
    [...itProvisioningKeys.all, 'requests', filters ?? {}] as const,
  request: (id: string) => [...itProvisioningKeys.all, 'request', id] as const,
  dashboard: () => [...itProvisioningKeys.all, 'dashboard'] as const,
  computerTypes: () => [...itProvisioningKeys.all, 'computer-types'] as const,
  readiness: (userId: string) => [...itProvisioningKeys.all, 'readiness', userId] as const,
  employee360: (userId: string) => [...itProvisioningKeys.all, '360', userId] as const,
  workstationDemand: () => [...itProvisioningKeys.all, 'workstation-demand'] as const,
};

export async function fetchComputerTypes(): Promise<{ code: string; label: string }[]> {
  const { data } = await apiClient.get('/it/provisioning/computer-types');
  return data;
}

export async function fetchProvisioningDashboard(): Promise<ProvisioningDashboard> {
  const { data } = await apiClient.get('/it/provisioning/dashboard');
  return data;
}

export async function fetchProvisioningRequests(params?: {
  status?: string;
  overdue_only?: boolean;
  computer_type?: string;
  user_id?: string;
}): Promise<ProvisioningRequest[]> {
  const { data } = await apiClient.get('/it/provisioning/requests', { params });
  return data;
}

export async function fetchProvisioningRequest(id: string): Promise<ProvisioningRequest> {
  const { data } = await apiClient.get(`/it/provisioning/requests/${id}`);
  return data;
}

export async function updateProvisioningStatus(
  id: string,
  payload: { status: string; assigned_it_user_id?: string; notes?: string },
): Promise<ProvisioningRequest> {
  const { data } = await apiClient.patch(`/it/provisioning/requests/${id}/status`, payload);
  return data;
}

export async function hireWithIt(
  payload: HireWithItPayload,
): Promise<{ user: User; provisioning: ProvisioningRequest; checklist_id?: string | null }> {
  const { data } = await apiClient.post('/it/provisioning/hire', payload);
  return data;
}

export async function fetchOnboardingReadiness(userId: string): Promise<OnboardingReadiness> {
  const { data } = await apiClient.get(`/it/provisioning/readiness/${userId}`);
  return data;
}

export async function fetchEmployee360(userId: string): Promise<Employee360> {
  const { data } = await apiClient.get(`/users/${userId}/360`);
  return data;
}

export async function fetchWorkstationDemandByShift(): Promise<
  {
    shift_id: string;
    shift_code: string;
    shift_name: string;
    shift_display: string;
    workstations_required: number;
  }[]
> {
  const { data } = await apiClient.get('/it/provisioning/workstation-demand-by-shift');
  return data;
}
