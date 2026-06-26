import axios from 'axios';
import { API_BASE_URL, getAccessToken } from './client';
import type {
  ImportJobProgress,
  ImportRunRequest,
  ImportRunResponse,
  ImportUploadResponse,
} from '../types/Import';

export async function uploadHistoricalProjects(file: File): Promise<ImportUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await axios.post<ImportUploadResponse>(
    `${API_BASE_URL}/imports/historical-projects/upload`,
    formData,
    {
      headers: {
        Authorization: `Bearer ${getAccessToken() ?? ''}`,
      },
    },
  );
  return data;
}

export async function runHistoricalImport(
  payload: ImportRunRequest,
): Promise<ImportRunResponse> {
  const { data } = await axios.post<ImportRunResponse>(
    `${API_BASE_URL}/imports/historical-projects/run`,
    payload,
    {
      headers: {
        Authorization: `Bearer ${getAccessToken() ?? ''}`,
        'Content-Type': 'application/json',
      },
    },
  );
  return data;
}

export async function fetchImportJob(jobId: string): Promise<ImportJobProgress> {
  const { data } = await axios.get<ImportJobProgress>(
    `${API_BASE_URL}/imports/historical-projects/jobs/${jobId}`,
    {
      headers: {
        Authorization: `Bearer ${getAccessToken() ?? ''}`,
      },
    },
  );
  return data;
}

export function getImportErrorLogUrl(jobId: string): string {
  return `${API_BASE_URL}/imports/historical-projects/jobs/${jobId}/errors.csv`;
}
