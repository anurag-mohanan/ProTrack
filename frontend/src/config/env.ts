/**
 * Environment-aware API and asset URL resolution.
 * Development uses relative /api/v1 via Vite proxy; production uses configured origins.
 */

const DEFAULT_API_PATH = '/api/v1';

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_URL;
  if (configured && String(configured).trim()) {
    return String(configured).replace(/\/$/, '');
  }
  return DEFAULT_API_PATH;
}

export function getApiOrigin(): string {
  const apiBase = getApiBaseUrl();
  if (apiBase.startsWith('/')) {
    if (typeof window !== 'undefined') {
      return window.location.origin;
    }
    return '';
  }
  return apiBase.replace(/\/api\/v1\/?$/, '');
}

export function resolveAssetUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:')) {
    return path;
  }
  const origin = getApiOrigin();
  if (!origin) return path.startsWith('/') ? path : `/${path}`;
  return `${origin}${path.startsWith('/') ? path : `/${path}`}`;
}

export const IS_PRODUCTION = import.meta.env.PROD;
export const IS_DEVELOPMENT = import.meta.env.DEV;
