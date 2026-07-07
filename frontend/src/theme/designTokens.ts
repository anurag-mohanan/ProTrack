/**
 * Phase 1 design tokens — centralized visual language for ProTrack.
 * Theme-ready: light values active; dark counterparts reserved in prosohmColorsDark.
 */

export const designTokens = {
  radius: {
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    pill: 999,
  },
  spacing: {
    cardPadding: 20,
    sectionGap: 24,
    gridGap: 24,
  },
  elevation: {
    card: '0 1px 3px rgba(15, 23, 42, 0.06), 0 4px 12px rgba(15, 23, 42, 0.04)',
    cardHover: '0 4px 16px rgba(15, 23, 42, 0.1), 0 8px 24px rgba(15, 23, 42, 0.06)',
    header: '0 1px 0 rgba(15, 23, 42, 0.06)',
    nav: '2px 0 12px rgba(15, 23, 42, 0.04)',
  },
  motion: {
    fast: '0.15s ease',
    normal: '0.22s ease',
    slow: '0.32s ease',
  },
  semantic: {
    primary: '#2563eb',
    primarySoft: '#eff6ff',
    success: '#16a34a',
    successSoft: '#f0fdf4',
    warning: '#d97706',
    warningSoft: '#fffbeb',
    danger: '#dc2626',
    dangerSoft: '#fef2f2',
    neutral: '#64748b',
    neutralSoft: '#f1f5f9',
    background: '#f4f7fb',
    card: '#ffffff',
    sidebar: '#0f172a',
    sidebarHover: 'rgba(255, 255, 255, 0.06)',
    sidebarActive: 'rgba(37, 99, 235, 0.18)',
  },
  stage: {
    preliminary: { main: '#6366f1', soft: '#eef2ff', label: 'Planning' },
    intermediate: { main: '#0ea5e9', soft: '#e0f2fe', label: 'Design' },
    final: { main: '#8b5cf6', soft: '#f5f3ff', label: 'Checking' },
  },
  health: {
    green: { main: '#16a34a', soft: '#dcfce7' },
    yellow: { main: '#d97706', soft: '#fef3c7' },
    red: { main: '#dc2626', soft: '#fee2e2' },
    grey: { main: '#94a3b8', soft: '#f1f5f9' },
  },
  utilization: {
    low: '#16a34a',
    medium: '#d97706',
    high: '#dc2626',
  },
} as const;

export type DesignHealthKey = keyof typeof designTokens.health;
