import { resolveAssetUrl as resolveAssetUrlFromEnv } from '../config/env';

/** Resolve uploaded asset paths against the API origin. */
export function resolveAssetUrl(path: string | null | undefined): string | null {
  return resolveAssetUrlFromEnv(path);
}

/** @deprecated Use resolveAssetUrl */
export function getAssetUrl(path: string | null | undefined): string | null {
  return resolveAssetUrlFromEnv(path);
}

export { getApiOrigin } from '../config/env';
