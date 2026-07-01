import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from '../services/authStorage';

/** Override with VITE_API_URL; defaults to backend direct URL per spec. */
export const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api/v1';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg ?? JSON.stringify(item)).join(', ');
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
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

  const raw = getErrorMessage(error).trim();
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
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const requestUrl = error.config?.url ?? '';
    if (
      error.response?.status === 401 &&
      requestUrl.includes('/auth/me')
    ) {
      clearAccessToken();
    }
    const message = getErrorMessage(error);
    const status = error.response?.status ?? 500;
    return Promise.reject(new ApiError(status, message));
  },
);

export { setAccessToken, clearAccessToken, getAccessToken };

export interface ListParams {
  skip?: number;
  limit?: number;
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
