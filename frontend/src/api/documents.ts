import { apiClient, buildQuery } from './client';

export type DocumentAsset = {
  id: string;
  entity_type: string;
  entity_id: string;
  title: string | null;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  storage_backend: string;
  storage_key: string;
  checksum: string | null;
  uploaded_by_id: string | null;
  notes: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export async function listDocuments(params?: {
  entity_type?: string;
  entity_id?: string;
}): Promise<DocumentAsset[]> {
  const { data } = await apiClient.get<DocumentAsset[]>(
    `/documents${buildQuery(params)}`,
  );
  return data;
}

export async function uploadDocument(payload: {
  entity_type: string;
  entity_id: string;
  file: File;
  title?: string;
  notes?: string;
}): Promise<DocumentAsset> {
  const formData = new FormData();
  formData.append('entity_type', payload.entity_type);
  formData.append('entity_id', payload.entity_id);
  formData.append('file', payload.file);
  if (payload.title) formData.append('title', payload.title);
  if (payload.notes) formData.append('notes', payload.notes);
  const { data } = await apiClient.post<DocumentAsset>('/documents', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export function documentDownloadUrl(documentId: string): string {
  return `/documents/${documentId}/download`;
}
