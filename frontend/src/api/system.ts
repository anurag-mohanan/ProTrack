import { apiClient } from './client';

export interface SystemHealth {
  backend_status: string;
  database_status: string;
  api_status: string;
  application_version: string;
  release_candidate: string;
  database_version: string | null;
  active_users: number;
  storage_usage_bytes: number;
  storage_usage_label: string;
  last_backup: string | null;
  import_queue: number;
  failed_jobs: number;
  failed_emails?: number;
  recent_errors: string[];
  internal_release: boolean;
}

export async function fetchSystemHealth(): Promise<SystemHealth> {
  const response = await apiClient.get<SystemHealth>('/system/health');
  return response.data;
}

export interface BackupEntry {
  filename: string;
  path: string;
  size_bytes: string;
  modified_at: string;
}

export interface SecurityPolicy {
  password_requirements: string;
  session_timeout_minutes: number;
  internal_release_mode: boolean;
}

export async function fetchBackups(): Promise<BackupEntry[]> {
  const { data } = await apiClient.get<BackupEntry[]>('/system/backups');
  return data;
}

export async function createBackup(): Promise<{ filename: string }> {
  const { data } = await apiClient.post<{ filename: string }>('/system/backups');
  return data;
}

export async function restoreBackup(filename: string): Promise<{ restored_from: string }> {
  const { data } = await apiClient.post<{ restored_from: string }>('/system/backups/restore', {
    filename,
  });
  return data;
}

export async function fetchSecurityPolicy(): Promise<SecurityPolicy> {
  const { data } = await apiClient.get<SecurityPolicy>('/system/security-policy');
  return data;
}
