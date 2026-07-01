/** Shared React Query cache durations for list/lookup data. */
export const QUERY_STALE_TIMES = {
  /** Project lists change more often than master data. */
  projects: 30_000,
  /** Lookups are stable within a session. */
  lookups: 5 * 60_000,
  notifications: 30_000,
  /** Dashboard summary is cached briefly to avoid duplicate calls on remount. */
  dashboard: 60_000,
} as const;
