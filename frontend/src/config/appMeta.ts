/** Central product branding and release metadata for ProTrack RC3. */

export const PRODUCT_NAME = 'ProTrack';
export const PRODUCT_TAGLINE = 'Engineering Management Platform';
export const COMPANY_LEGAL_NAME = 'Prosohm Projects Pvt. Ltd.';
export const COMPANY_BYLINE = `by ${COMPANY_LEGAL_NAME}`;

export const APP_VERSION = import.meta.env.VITE_APP_VERSION ?? '1.0.0';
export const RELEASE_CANDIDATE = import.meta.env.VITE_RELEASE_CANDIDATE ?? 'RC3';
export const RELEASE_LABEL = import.meta.env.VITE_RELEASE_LABEL ?? 'Internal Release';

export const VERSION_DISPLAY = `v${APP_VERSION} ${RELEASE_CANDIDATE}`;
export const COPYRIGHT_YEAR = 2026;
export const COPYRIGHT_NOTICE = `© ${COPYRIGHT_YEAR} ${COMPANY_LEGAL_NAME}`;

export const PRODUCTION_FRONTEND_URL =
  import.meta.env.VITE_APP_URL ?? 'https://protrack.prosohm.com';
export const PRODUCTION_API_URL =
  import.meta.env.VITE_API_URL ?? 'https://api.protrack.prosohm.com/api/v1';
