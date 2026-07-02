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
  recent_errors: string[];
  internal_release: boolean;
}

export async function fetchSystemHealth(): Promise<SystemHealth> {
  const response = await apiClient.get<SystemHealth>('/system/health');
  return response.data;
}
