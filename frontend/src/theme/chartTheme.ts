/**
 * Modern minimal chart palette for Engineering Dashboard.
 * Cool slate base, soft semantic accents — avoids neon stoplight and muddy purple stacks.
 */
export const chartTheme = {
  surface: {
    card: '#ffffff',
    muted: '#f8fafc',
    hairline: 'rgba(15, 23, 42, 0.06)',
    track: '#eef2f6',
  },
  ink: {
    primary: '#0f172a',
    secondary: '#64748b',
    tertiary: '#94a3b8',
  },
  /** Ranked intensity for customer workload (darker = higher hours). */
  workload: ['#94a3b8', '#64748b', '#475569', '#334155', '#1e293b', '#0f172a'],
  hours: {
    billable: '#0f766e',
    billableSoft: '#ccfbf1',
    nonBillable: '#0369a1',
    nonBillableSoft: '#e0f2fe',
    np: '#b45309',
    npSoft: '#ffedd5',
  },
  stage: {
    preliminary: '#64748b',
    intermediate: '#0d9488',
    final: '#1d4ed8',
  },
  health: {
    green: '#059669',
    greenSoft: '#ecfdf5',
    yellow: '#d97706',
    yellowSoft: '#fffbeb',
    red: '#e11d48',
    redSoft: '#fff1f2',
    grey: '#94a3b8',
    greySoft: '#f1f5f9',
  },
  utilization: {
    low: '#0d9488',
    medium: '#d97706',
    high: '#e11d48',
    track: '#eef2f6',
  },
  availability: {
    open: '#059669',
    openSoft: '#ecfdf5',
    assigned: '#0369a1',
    assignedSoft: '#e0f2fe',
    leave: '#64748b',
    leaveSoft: '#f1f5f9',
  },
} as const;
