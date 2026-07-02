import { apiClient } from './client';
import type { DeleteCheckResult } from '../components/ui/design-system/DeleteRecordDialog';

export async function fetchDeleteCheck(
  resource: string,
  recordId: string,
): Promise<DeleteCheckResult> {
  const { data } = await apiClient.get<DeleteCheckResult>(`/${resource}/${recordId}/delete-check`);
  return data;
}

export async function permanentDeleteResource(resource: string, recordId: string): Promise<void> {
  await apiClient.delete(`/${resource}/${recordId}`);
}

export async function permanentDeleteUser(userId: string): Promise<void> {
  await apiClient.delete(`/users/${userId}/permanent`);
}

export async function fetchDeletedUsers(): Promise<import('../types').User[]> {
  const { data } = await apiClient.get<import('../types').User[]>('/users/deleted');
  return data;
}

export async function restoreDeletedUser(userId: string): Promise<import('../types').User> {
  const { data } = await apiClient.post<import('../types').User>(
    `/users/${userId}/restore-deleted`,
  );
  return data;
}

export async function fetchUserDeleteCheck(userId: string): Promise<DeleteCheckResult> {
  const { data } = await apiClient.get<{
    can_permanently_delete: boolean;
    blockers: string[];
  }>(`/users/${userId}/delete-check`);
  return {
    can_delete: data.can_permanently_delete,
    blockers: data.blockers,
    record_name: null,
    record_type: 'User',
    related_records: data.blockers,
  };
}
