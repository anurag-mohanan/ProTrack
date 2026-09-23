import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { getApiBaseUrl } from '../config/env';
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from '../services/authStorage';

/** Resolved from VITE_API_URL; defaults to same-origin /api/v1 in development. */
export const API_BASE_URL = getApiBaseUrl();

export class ApiError extends Error {
  status: number;
  /** Request path relative to API base (when known). */
  url?: string;
  /** Raw FastAPI `detail` payload when present. */
  detail?: unknown;
  /** Full response body for diagnostics. */
  body?: unknown;

  constructor(
    status: number,
    message: string,
    opts?: { url?: string; detail?: unknown; body?: unknown },
  ) {
    super(message);
    this.status = status;
    this.url = opts?.url;
    this.detail = opts?.detail;
    this.body = opts?.body;
  }
}

function formatDetailPayload(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail.trim();
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg: unknown }).msg);
        }
        return JSON.stringify(item);
      })
      .filter(Boolean)
      .join('; ');
  }
  if (detail && typeof detail === 'object') {
    const obj = detail as Record<string, unknown>;
    const parts: string[] = [];
    if (typeof obj.message === 'string' && obj.message.trim()) parts.push(obj.message.trim());
    if (typeof obj.error_code === 'string' && obj.error_code.trim()) {
      parts.push(`code=${obj.error_code.trim()}`);
    }
    if (typeof obj.stage === 'string' && obj.stage.trim()) {
      parts.push(`stage=${obj.stage.trim()}`);
    }
    if (typeof obj.details === 'string' && obj.details.trim()) parts.push(obj.details.trim());
    if (parts.length) return parts.join(' · ');
  }
  return null;
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    const fromDetail = formatDetailPayload(detail);
    if (fromDetail) return fromDetail;
    if (error.response?.status === 409) {
      return 'This record already exists or conflicts with existing data.';
    }
    if (error.response?.status === 404) {
      return 'The requested record could not be found.';
    }
    if (error.response?.status && error.response.status >= 500) {
      const status = error.response.status;
      const url = error.config?.url ?? '';
      const bodyPreview =
        typeof error.response.data === 'string'
          ? error.response.data.slice(0, 240)
          : error.response.data != null
            ? JSON.stringify(error.response.data).slice(0, 240)
            : '';
      const bits = [`HTTP ${status}`];
      if (url) bits.push(url);
      if (bodyPreview) bits.push(bodyPreview);
      return `PDF extraction / API failed (${bits.join(' · ')}). Check server logs.`;
    }
    if (error.code === 'ECONNABORTED' || /timeout/i.test(error.message)) {
      return `Request timed out${error.config?.url ? ` (${error.config.url})` : ''}. The document analysis may need more time.`;
    }
    if (error.code === 'ERR_CANCELED' || /cancel/i.test(error.message)) {
      return 'Request was cancelled before the server responded.';
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
}

function normalizeValidationMessage(message: string): string {
  const normalized = message.toLowerCase();
  if (normalized.includes('invalid uuid')) return 'Please select a valid value.';
  if (normalized.includes('field required')) return 'Please complete all required fields.';
  if (normalized.includes('tool_number') && normalized.includes('exists')) {
    return 'A project with this Tool Number already exists.';
  }
  if (normalized.includes('validation failed')) {
    return 'Please review the highlighted fields and try again.';
  }
  return message;
}

export function getUserFriendlyErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Your session has expired. Please sign in again.';
    }
    if (error.status === 403) {
      return 'You do not have permission to view this information.';
    }
    if (error.status === 404) {
      return 'The requested information could not be found.';
    }
    if (error.status >= 500) {
      return 'Something went wrong. Please try again in a moment.';
    }
  }

  const raw = normalizeValidationMessage(getErrorMessage(error).trim());
  const normalized = raw.toLowerCase();
  if (!raw) {
    return 'Something went wrong. Please try again.';
  }
  if (normalized.includes('network error') || normalized.includes('failed to fetch')) {
    return 'Unable to reach the server. Check your connection and try again.';
  }
  if (normalized.includes('record not found') || normalized.includes('not found')) {
    return 'The requested information could not be found.';
  }
  if (normalized.includes('insufficient permissions') || normalized.includes('forbidden')) {
    return 'You do not have permission to perform this action.';
  }
  if (normalized.includes('validation') || normalized.includes('required')) {
    return raw;
  }
  return 'Something went wrong. Please try again.';
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Never force JSON on FormData — FastAPI needs multipart with boundary.
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    if (typeof config.headers.delete === 'function') {
      config.headers.delete('Content-Type');
    } else {
      delete (config.headers as Record<string, unknown>)['Content-Type'];
    }
  } else if (
    config.data != null &&
    typeof config.data === 'object' &&
    !(typeof FormData !== 'undefined' && config.data instanceof FormData)
  ) {
    const current = config.headers.get?.('Content-Type') ?? (config.headers as Record<string, unknown>)['Content-Type'];
    if (!current) {
      config.headers.set('Content-Type', 'application/json');
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: unknown }>) => {
    const requestUrl = error.config?.url ?? '';
    if (
      error.response?.status === 401 &&
      requestUrl.includes('/auth/me')
    ) {
      clearAccessToken();
    }
    const message = getErrorMessage(error);
    const status = error.response?.status ?? 500;
    if (typeof console !== 'undefined' && console.error) {
      console.error('[ProTrack API error]', {
        status,
        url: requestUrl,
        method: error.config?.method,
        detail: error.response?.data?.detail,
        body: error.response?.data,
        axiosMessage: error.message,
        code: error.code,
      });
    }
    return Promise.reject(
      new ApiError(status, message, {
        url: requestUrl,
        detail: error.response?.data?.detail,
        body: error.response?.data,
      }),
    );
  },
);

export { setAccessToken, clearAccessToken, getAccessToken };

export interface ListParams {
  page?: number;
  page_size?: number;
  skip?: number;
  limit?: number;
  sort?: string;
  [key: string]: string | number | boolean | string[] | undefined;
}

export function buildQuery(params?: ListParams): string {
  if (!params) return '';
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === '') return;
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item) search.append(key, String(item));
      });
      return;
    }
    search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}
