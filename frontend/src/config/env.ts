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

/**
 * Resolve the company logo URL through the API path. Serving via /api/v1
 * guarantees the logo is reachable in every deployment (including behind IIS
 * reverse proxies that only forward /api to the backend), avoiding the
 * intermittent placeholder caused by the /uploads static mount not being routed.
 * The optional version token busts the browser cache when the logo changes.
 */
export function resolveLogoUrl(
  logoPath: string | null | undefined,
  version?: string | number,
): string | null {
  if (!logoPath) return null;
  if (logoPath.startsWith('data:')) return logoPath;
  const base = getApiBaseUrl().replace(/\/$/, '');
  const url = `${base}/settings/company/logo`;
  return version !== undefined && version !== null && version !== ''
    ? `${url}?v=${encodeURIComponent(String(version))}`
    : url;
}

export const IS_PRODUCTION = import.meta.env.PROD;
export const IS_DEVELOPMENT = import.meta.env.DEV;

/** When true, forced password change redirects are bypassed (internal soft launch). */
export function isInternalRelease(): boolean {
  const value = import.meta.env.VITE_INTERNAL_RELEASE;
  if (value === undefined || value === '') {
    return true;
  }
  return String(value).toLowerCase() === 'true' || value === '1';
}

export function requiresForcedPasswordChange(mustChangePassword: boolean | undefined): boolean {
  return Boolean(mustChangePassword) && !isInternalRelease();
}
