import { apiClient, buildQuery } from './client';
import type { PaginatedResponse } from '../types/pagination';
import { isPaginatedResponse, unwrapListResponse } from '../types/pagination';

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
  page?: number;
  page_size?: number;
  skip?: number;
  limit?: number;
}): Promise<ActivityRead[]> {
  const { data } = await apiClient.get<ActivityRead[] | PaginatedResponse<ActivityRead>>(
    `/activities${buildQuery(options)}`,
  );
  return unwrapListResponse(data);
}

export async function fetchAuditLogsPaginated(options?: {
  page?: number;
  page_size?: number;
  skip?: number;
  limit?: number;
}): Promise<PaginatedResponse<ActivityRead>> {
  const { data } = await apiClient.get<ActivityRead[] | PaginatedResponse<ActivityRead>>(
    `/activities${buildQuery(options)}`,
  );
  if (isPaginatedResponse<ActivityRead>(data)) {
    return data;
  }
  return {
    items: data,
    total: data.length,
    page: 1,
    page_size: data.length || options?.page_size || options?.limit || 25,
    pages: 1,
  };
}
