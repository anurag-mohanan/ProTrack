import type { UserPreferences } from '../types/Preferences';
import { apiClient } from './client';

export interface UserProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string | null;
  designation?: string | null;
  role_id: string;
  role_name: string;
  team_id?: string | null;
  team_name?: string | null;
  department_id?: string | null;
  department_name?: string | null;
  manager_id?: string | null;
  manager_name?: string | null;
  is_active: boolean;
  employment_type?: string | null;
  working_hours_per_day: number;
  working_days: string;
  availability_status: string;
  skills: Array<{ skill_id: string; skill_name?: string | null; proficiency: string }>;
  summary: {
    active_projects: number;
    quoted_hours_assigned: number;
    actual_hours_logged: number;
    utilization_percent: number;
    timesheet_count: number;
  };
  preferences: Omit<UserPreferences, 'id' | 'user_id' | 'created_at' | 'updated_at'>;
}

export async function fetchMyPreferences(): Promise<UserPreferences> {
  const { data } = await apiClient.get<UserPreferences>('/preferences/me');
  return data;
}

export async function updateMyPreferences(
  payload: Partial<UserPreferences>,
): Promise<UserPreferences> {
  const { data } = await apiClient.patch<UserPreferences>('/preferences/me', payload);
  return data;
}

export async function fetchMyProfile(): Promise<UserProfile> {
  const { data } = await apiClient.get<UserProfile>('/auth/me/profile');
  return data;
}

export async function changePassword(payload: {
  current_password: string;
  new_password: string;
  confirm_password: string;
}): Promise<void> {
  await apiClient.post('/auth/change-password', payload);
}
