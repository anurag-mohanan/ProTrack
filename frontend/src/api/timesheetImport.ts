import axios from 'axios';
import { API_BASE_URL, getAccessToken } from './client';
import type {
  FolderBatchUploadResponse,
  FolderImportJobProgress,
  FolderImportRunResponse,
  FolderScanResponse,
} from '../types/TimesheetFolderImport';
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

export async function uploadHistoricalTimesheetFolder(
  files: File[],
  paths: string[],
): Promise<FolderBatchUploadResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  paths.forEach((path) => formData.append('paths', path));
  const { data } = await axios.post<FolderBatchUploadResponse>(
    `${BASE}/folder/upload`,
    formData,
    { headers: authHeaders() },
  );
  return data;
}

export async function scanHistoricalTimesheetFolder(payload: {
  batch_id?: string;
  source_path?: string;
}): Promise<FolderScanResponse> {
  const { data } = await axios.post<FolderScanResponse>(`${BASE}/folder/scan`, payload, {
    headers: authHeaders('application/json'),
  });
  return data;
}

export async function runHistoricalTimesheetFolderImport(payload: {
  batch_id?: string;
  source_path?: string;
}): Promise<FolderImportRunResponse> {
  const { data } = await axios.post<FolderImportRunResponse>(`${BASE}/folder/run`, payload, {
    headers: authHeaders('application/json'),
  });
  return data;
}

export async function fetchFolderImportJob(jobId: string): Promise<FolderImportJobProgress> {
  const { data } = await axios.get<FolderImportJobProgress>(`${BASE}/folder/jobs/${jobId}`, {
    headers: authHeaders(),
  });
  return data;
}

export async function cancelFolderImportJob(jobId: string): Promise<void> {
  await axios.post(`${BASE}/folder/jobs/${jobId}/cancel`, {}, {
    headers: authHeaders('application/json'),
  });
}

export function getFolderImportLogUrl(jobId: string): string {
  return `${BASE}/folder/jobs/${jobId}/log.xlsx`;
}

export async function downloadFolderImportLog(
  jobId: string,
  filename = 'HistoricalImportLog.xlsx',
): Promise<void> {
  const response = await fetch(getFolderImportLogUrl(jobId), {
    headers: {
      Authorization: `Bearer ${getAccessToken() ?? ''}`,
    },
  });
  if (!response.ok) {
    throw new Error('Failed to download import log.');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
