import type {
  BrandingSettings,
  CompanySettings,
  ContactType,
  Department,
  EmailSettings,
  EmailTemplate,
  EngineeringDiscipline,
  FilePathSettings,
  Holiday,
  LegalEntity,
  NotificationSettings,
  PublicSettings,
  Skill,
  TimesheetPolicySettings,
} from '../types/Settings';
import { apiClient } from './client';
import { setTimesheetLockPolicy } from '../utils/timesheetLocking';

export async function fetchPublicSettings(): Promise<PublicSettings> {
  const { data } = await apiClient.get<PublicSettings>('/settings/public');
  return data;
}

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

export async function uploadCompanyLogo(file: File): Promise<CompanySettings> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await apiClient.post<CompanySettings>('/settings/company/logo', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function fetchBrandingSettings(): Promise<BrandingSettings> {
  const { data } = await apiClient.get<BrandingSettings>('/settings/branding');
  return data;
}

export async function updateBrandingSettings(
  payload: Partial<BrandingSettings>,
): Promise<BrandingSettings> {
  const { data } = await apiClient.patch<BrandingSettings>('/settings/branding', payload);
  return data;
}

export async function restoreBrandingDefaults(): Promise<BrandingSettings> {
  const { data } = await apiClient.post<BrandingSettings>('/settings/branding/restore-defaults');
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

export async function fetchTimesheetPolicySettings(): Promise<TimesheetPolicySettings> {
  const { data } = await apiClient.get<TimesheetPolicySettings>('/settings/timesheet-policy');
  setTimesheetLockPolicy({
    editableMonthsBack: data.editable_months_back,
    softLockEnabled: data.soft_lock_enabled,
    hardLockMessage: data.hard_lock_message,
    softLockMessage: data.soft_lock_message,
  });
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

export async function fetchEmailSettings(): Promise<EmailSettings> {
  const { data } = await apiClient.get<EmailSettings>('/settings/email');
  return data;
}

export async function updateEmailSettings(
  payload: Partial<EmailSettings> & { smtp_password?: string },
): Promise<EmailSettings> {
  const { data } = await apiClient.patch<EmailSettings>('/settings/email', payload);
  return data;
}

export async function sendEmailTest(to_address: string): Promise<void> {
  await apiClient.post('/settings/email/test', { to_address });
}

export async function fetchEmailTemplates(): Promise<EmailTemplate[]> {
  const { data } = await apiClient.get<EmailTemplate[]>('/settings/email/templates');
  return data;
}

export async function updateEmailTemplate(
  templateId: string,
  payload: Partial<Pick<EmailTemplate, 'subject' | 'body_html' | 'body_text' | 'is_enabled' | 'name' | 'description'>>,
): Promise<EmailTemplate> {
  const { data } = await apiClient.patch<EmailTemplate>(
    `/settings/email/templates/${templateId}`,
    payload,
  );
  return data;
}

export async function fetchLegalEntities(): Promise<LegalEntity[]> {
  const { data } = await apiClient.get<LegalEntity[]>('/settings/legal-entities');
  return data;
}
