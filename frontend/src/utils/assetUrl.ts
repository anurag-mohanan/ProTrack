/** Resolve uploaded asset paths against the API origin (not /api/v1). */
export function getAssetUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:')) {
    return path;
  }
  const apiBase = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8002/api/v1';
  const origin = apiBase.replace(/\/api\/v1\/?$/, '');
  return `${origin}${path.startsWith('/') ? path : `/${path}`}`;
}

export function getApiOrigin(): string {
  const apiBase = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8002/api/v1';
  return apiBase.replace(/\/api\/v1\/?$/, '');
}
