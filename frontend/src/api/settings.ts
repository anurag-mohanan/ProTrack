import type {
  CompanySettings,
  ContactType,
  Department,
  EngineeringDiscipline,
  FilePathSettings,
  Holiday,
  NotificationSettings,
  Skill,
} from '../types/Settings';
import { apiClient } from './client';

export async function fetchCompanySettings(): Promise<CompanySettings> {
  const { data } = await apiClient.get<CompanySettings>('/settings/company');
  return data;
}

export async function updateCompanySettings(
  payload: Partial<CompanySettings>,
): Promise<CompanySettings> {
  const { data } = await apiClient.patch<CompanySettings>('/settings/company', payload);
  return data;
}

export async function fetchHolidays(): Promise<Holiday[]> {
  const { data } = await apiClient.get<Holiday[]>('/settings/holidays');
  return data;
}

export async function createHoliday(payload: Omit<Holiday, 'id' | 'created_at' | 'updated_at'>) {
  const { data } = await apiClient.post<Holiday>('/settings/holidays', payload);
  return data;
}

export async function deleteHoliday(id: string) {
  await apiClient.delete(`/settings/holidays/${id}`);
}

export async function fetchContactTypes(): Promise<ContactType[]> {
  const { data } = await apiClient.get<ContactType[]>('/settings/contact-types');
  return data;
}

export async function fetchDepartments(): Promise<Department[]> {
  const { data } = await apiClient.get<Department[]>('/settings/departments');
  return data;
}

export async function fetchSkills(): Promise<Skill[]> {
  const { data } = await apiClient.get<Skill[]>('/settings/skills');
  return data;
}

export async function fetchDisciplines(): Promise<EngineeringDiscipline[]> {
  const { data } = await apiClient.get<EngineeringDiscipline[]>('/settings/disciplines');
  return data;
}

export async function fetchFilePathSettings(): Promise<FilePathSettings> {
  const { data } = await apiClient.get<FilePathSettings>('/settings/file-paths');
  return data;
}

export async function updateFilePathSettings(
  payload: Partial<FilePathSettings>,
): Promise<FilePathSettings> {
  const { data } = await apiClient.patch<FilePathSettings>('/settings/file-paths', payload);
  return data;
}

export async function fetchNotificationSettings(): Promise<NotificationSettings> {
  const { data } = await apiClient.get<NotificationSettings>('/settings/notifications');
  return data;
}

export async function updateNotificationSettings(
  payload: Partial<NotificationSettings>,
): Promise<NotificationSettings> {
  const { data } = await apiClient.patch<NotificationSettings>(
    '/settings/notifications',
    payload,
  );
  return data;
}
