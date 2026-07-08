import { apiClient, buildQuery } from './client';

export interface ActivityRead {
  id: string;
  user_id?: string | null;
  user_name?: string | null;
  entity_type?: string | null;
  entity_id?: string | null;
  action: string;
  old_value?: string | null;
  new_value?: string | null;
  created_at: string;
  updated_at?: string;
}

export async function fetchAuditLogs(options?: {
  skip?: number;
  limit?: number;
}): Promise<ActivityRead[]> {
  const { data } = await apiClient.get<ActivityRead[]>(`/activities${buildQuery(options)}`);
  return data;
}
