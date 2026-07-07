/**
 * Prosohm brand palette extracted from https://www.prosohm.com/
 * Primary teal (#1abc9c), dark engineering navy (#2c3e50), accent red (#e42c3e).
 */

export const prosohmColors = {
  primary: {
    main: '#2563eb',
    light: '#60a5fa',
    dark: '#1d4ed8',
    contrastText: '#ffffff',
  },
  secondary: {
    main: '#2c3e50',
    light: '#3d566e',
    dark: '#1f4037',
    contrastText: '#ffffff',
  },
  accent: {
    main: '#e42c3e',
    light: '#ee9ca7',
    dark: '#c0392b',
    contrastText: '#ffffff',
  },
  success: {
    main: '#28a745',
    light: '#99f2c8',
    dark: '#1e7e34',
    contrastText: '#ffffff',
  },
  warning: {
    main: '#F3904F',
    light: '#ffdde1',
    dark: '#e67e22',
    contrastText: '#2c3e50',
  },
  error: {
    main: '#dc3545',
    light: '#f8d7da',
    dark: '#bd2130',
    contrastText: '#ffffff',
  },
  info: {
    main: '#17a2b8',
    light: '#6dd5fa',
    dark: '#117a8b',
    contrastText: '#ffffff',
  },
  neutral: {
    white: '#ffffff',
    background: '#f4f7fb',
    surface: '#ffffff',
    card: '#ffffff',
    sidebar: '#0f172a',
    sidebarDark: '#0b1220',
    header: '#ffffff',
    border: '#e5e5e5',
    borderLight: '#eaeff5',
    divider: '#dee2e6',
    hover: 'rgba(26, 188, 156, 0.08)',
    selected: 'rgba(26, 188, 156, 0.14)',
    sidebarActive: 'rgba(26, 188, 156, 0.16)',
    sidebarDivider: 'rgba(255, 255, 255, 0.08)',
    sidebarOverlayTop: 'rgba(255, 255, 255, 0.03)',
    sidebarOverlayBottom: 'rgba(0, 0, 0, 0.08)',
    textPrimary: '#2c3e50',
    textSecondary: '#6c757d',
    textMuted: '#94a3b8',
    textOnDark: '#ffffff',
    textOnDarkMuted: 'rgba(255, 255, 255, 0.72)',
  },
  /** Shadow opacities applied against secondary.main in the theme builder. */
  shadow: {
    card: 0.06,
    cardHover: 0.12,
    header: 0.06,
    dialog: 0.16,
    logo: 0.2,
  },
} as const;

/** Dark-mode tokens reserved for a future theme toggle. */
export const prosohmColorsDark = {
  primary: prosohmColors.primary,
  secondary: {
    main: '#1a252f',
    light: '#243342',
    dark: '#111820',
    contrastText: '#ffffff',
  },
  accent: prosohmColors.accent,
  success: prosohmColors.success,
  warning: prosohmColors.warning,
  error: prosohmColors.error,
  info: prosohmColors.info,
  neutral: {
    white: '#ffffff',
    background: '#121820',
    surface: '#1a252f',
    card: '#1e2a36',
    sidebar: '#111820',
    sidebarDark: '#0d1218',
    header: '#1a252f',
    border: '#2d3a47',
    borderLight: '#243342',
    divider: '#2d3a47',
    hover: 'rgba(26, 188, 156, 0.12)',
    selected: 'rgba(26, 188, 156, 0.2)',
    textPrimary: '#f1f5f9',
    textSecondary: '#94a3b8',
    textMuted: '#64748b',
    textOnDark: '#ffffff',
    textOnDarkMuted: 'rgba(255, 255, 255, 0.72)',
    sidebarActive: 'rgba(26, 188, 156, 0.2)',
    sidebarDivider: 'rgba(255, 255, 255, 0.08)',
    sidebarOverlayTop: 'rgba(255, 255, 255, 0.04)',
    sidebarOverlayBottom: 'rgba(0, 0, 0, 0.16)',
  },
  shadow: prosohmColors.shadow,
} as const;

export type ProsohmColorMode = 'light' | 'dark';
