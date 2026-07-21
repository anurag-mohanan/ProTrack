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

// --- Security Center --------------------------------------------------------

export interface SecurityPolicySettings {
  password_min_length: number;
  password_expiry_days: number;
  password_history_count: number;
  lockout_max_failed_attempts: number;
  lockout_duration_minutes: number;
  session_idle_timeout_minutes: number;
  audit_retention_days: number;
}

export interface SecurityEvent {
  action: string;
  outcome: string | null;
  module: string | null;
  ip_address: string | null;
  user_id: string | null;
  created_at: string | null;
}

export interface SecurityOverview {
  security_score: number;
  failed_logins_24h: number;
  locked_accounts: number;
  active_sessions: number;
  recent_permission_changes: number;
  export_events_7d: number;
  last_backup_at: string | null;
  last_backup_filename: string | null;
  secret_ok: boolean;
  encryption_ok: boolean;
  hsts_enabled: boolean;
  rate_limiting_enabled: boolean;
  config_warnings: string[];
  recent_events: SecurityEvent[];
}

export interface ActiveSession {
  id: string;
  user_id: string;
  user_name: string | null;
  user_email: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string | null;
  last_seen_at: string | null;
  expires_at: string | null;
}

export async function fetchSecurityOverview(): Promise<SecurityOverview> {
  const { data } = await apiClient.get<SecurityOverview>('/admin/security/overview');
  return data;
}

export async function fetchSecurityPolicySettings(): Promise<SecurityPolicySettings> {
  const { data } = await apiClient.get<SecurityPolicySettings>('/admin/security/policy');
  return data;
}

export async function updateSecurityPolicySettings(
  payload: Partial<SecurityPolicySettings>,
): Promise<SecurityPolicySettings> {
  const { data } = await apiClient.put<SecurityPolicySettings>('/admin/security/policy', payload);
  return data;
}

export async function fetchActiveSessions(): Promise<ActiveSession[]> {
  const { data } = await apiClient.get<ActiveSession[]>('/admin/security/sessions');
  return data;
}

export async function terminateUserSessions(userId: string): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>(
    `/admin/security/sessions/${userId}/terminate`,
  );
  return data;
}
