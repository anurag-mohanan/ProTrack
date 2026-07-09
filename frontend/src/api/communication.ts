import { apiClient } from './client';
import type { PaginatedResponse } from '../types/pagination';
import { isPaginatedResponse, unwrapListResponse } from '../types/pagination';

export interface EmailAttachmentMeta {
  name: string;
  path?: string | null;
  mime_type?: string | null;
}

export interface EmailMessage {
  id: string;
  project_id?: string | null;
  sent_by_user_id?: string | null;
  template_slug?: string | null;
  to_addresses: string[];
  subject: string;
  body_html: string;
  body_text?: string | null;
  status: string;
  retry_count: number;
  max_retries: number;
  last_error?: string | null;
  smtp_response?: string | null;
  attachments: EmailAttachmentMeta[];
  recipients_display?: string | null;
  timeline_label?: string | null;
  sent_at?: string | null;
  delivered_at?: string | null;
  created_at: string;
}

export interface EmailPreviewPayload {
  subject: string;
  body_html: string;
  body_text?: string | null;
  context?: Record<string, string>;
}

export async function fetchEmailQueue(params?: {
  status?: string;
  search?: string;
  page?: number;
  page_size?: number;
}): Promise<EmailMessage[]> {
  const { data } = await apiClient.get<EmailMessage[] | PaginatedResponse<EmailMessage>>(
    '/emails/queue',
    { params },
  );
  return unwrapListResponse(data);
}

export async function fetchEmailQueuePaginated(params?: {
  status?: string;
  search?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<EmailMessage>> {
  const { data } = await apiClient.get<EmailMessage[] | PaginatedResponse<EmailMessage>>(
    '/emails/queue',
    { params },
  );
  if (isPaginatedResponse<EmailMessage>(data)) {
    return data;
  }
  return {
    items: data,
    total: data.length,
    page: 1,
    page_size: data.length || params?.page_size || 25,
    pages: 1,
  };
}

export async function fetchEmailHistory(params?: {
  project_id?: string;
  search?: string;
}): Promise<EmailMessage[]> {
  const { data } = await apiClient.get<EmailMessage[]>('/emails/history', { params });
  return data;
}

export async function fetchProjectCommunications(
  projectId: string,
  search?: string,
): Promise<EmailMessage[]> {
  const { data } = await apiClient.get<EmailMessage[]>(`/projects/${projectId}/communications`, {
    params: search ? { search } : undefined,
  });
  return data;
}

export async function previewEmailTemplate(
  payload: EmailPreviewPayload,
): Promise<{ subject: string; body_html: string; body_text?: string | null }> {
  const { data } = await apiClient.post('/emails/preview', payload);
  return data;
}

export async function fetchEmailTemplateVariables(): Promise<string[]> {
  const { data } = await apiClient.get<{ variables: string[] }>('/emails/variables');
  return data.variables;
}

export async function processEmailQueue(): Promise<{ processed: number }> {
  const { data } = await apiClient.post<{ processed: number }>('/emails/queue/process');
  return data;
}

export async function sendOneClickEmail(payload: {
  project_id: string;
  action: string;
  message?: string;
  extra_addresses?: string[];
  attach_released_files?: boolean;
}): Promise<void> {
  await apiClient.post('/emails/one-click', payload);
}

export async function sendCustomerEmail(payload: {
  project_id: string;
  template_slug: string;
  message: string;
  to_addresses?: string[];
  attachment_paths?: string[];
}): Promise<void> {
  await apiClient.post('/emails/customer', payload);
}

export async function testEmailConnection(): Promise<{
  success: boolean;
  status?: string | null;
  message?: string | null;
}> {
  const { data } = await apiClient.post('/settings/email/test-connection');
  return data;
}

export async function applyZohoDefaults(): Promise<void> {
  await apiClient.post('/settings/email/apply-zoho-defaults');
}
