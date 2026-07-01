import axios from 'axios';
import { API_BASE_URL, getAccessToken } from './client';
import type {
  TimesheetImportHistoryDetail,
  TimesheetImportHistoryRead,
  TimesheetImportJobProgress,
  TimesheetImportResolveRequest,
  TimesheetImportRunRequest,
  TimesheetImportRunResponse,
  TimesheetImportUploadResponse,
  TimesheetImportValidateResponse,
} from '../types/TimesheetImport';

const BASE = `${API_BASE_URL}/imports/historical-timesheets`;

function authHeaders(contentType?: string) {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${getAccessToken() ?? ''}`,
  };
  if (contentType) {
    headers['Content-Type'] = contentType;
  }
  return headers;
}

export async function uploadHistoricalTimesheet(
  file: File,
): Promise<TimesheetImportUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await axios.post<TimesheetImportUploadResponse>(
    `${BASE}/upload`,
    formData,
    { headers: authHeaders() },
  );
  return data;
}

export async function previewTimesheetUpload(
  uploadId: string,
): Promise<TimesheetImportUploadResponse> {
  const { data } = await axios.get<TimesheetImportUploadResponse>(
    `${BASE}/upload/${uploadId}/preview`,
    { headers: authHeaders() },
  );
  return data;
}

export async function validateTimesheetUpload(
  uploadId: string,
): Promise<TimesheetImportValidateResponse> {
  const { data } = await axios.post<TimesheetImportValidateResponse>(
    `${BASE}/upload/${uploadId}/validate`,
    {},
    { headers: authHeaders('application/json') },
  );
  return data;
}

export async function resolveTimesheetUpload(
  payload: TimesheetImportResolveRequest,
): Promise<void> {
  await axios.post(`${BASE}/upload/${payload.upload_id}/resolve`, payload, {
    headers: authHeaders('application/json'),
  });
}

export async function runHistoricalTimesheetImport(
  payload: TimesheetImportRunRequest,
): Promise<TimesheetImportRunResponse> {
  const { data } = await axios.post<TimesheetImportRunResponse>(`${BASE}/run`, payload, {
    headers: authHeaders('application/json'),
  });
  return data;
}

export async function fetchTimesheetImportJob(
  jobId: string,
): Promise<TimesheetImportJobProgress> {
  const { data } = await axios.get<TimesheetImportJobProgress>(`${BASE}/jobs/${jobId}`, {
    headers: authHeaders(),
  });
  return data;
}

export function getTimesheetImportErrorLogUrl(jobId: string): string {
  return `${BASE}/jobs/${jobId}/errors.csv`;
}

export async function fetchTimesheetImportHistory(): Promise<TimesheetImportHistoryRead[]> {
  const { data } = await axios.get<TimesheetImportHistoryRead[]>(`${BASE}/history`, {
    headers: authHeaders(),
  });
  return data;
}

export async function fetchTimesheetImportHistoryDetail(
  historyId: string,
): Promise<TimesheetImportHistoryDetail> {
  const { data } = await axios.get<TimesheetImportHistoryDetail>(
    `${BASE}/history/${historyId}`,
    { headers: authHeaders() },
  );
  return data;
}

export async function reimportTimesheetHistory(
  historyId: string,
): Promise<TimesheetImportRunResponse> {
  const { data } = await axios.post<TimesheetImportRunResponse>(
    `${BASE}/history/${historyId}/re-import`,
    {},
    { headers: authHeaders('application/json') },
  );
  return data;
}
