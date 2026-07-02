import { alpha, createTheme, type Theme, type ThemeOptions } from '@mui/material/styles';
import type { BrandingSettings } from '../types/Settings';
import type { UserPreferences } from '../types/Preferences';
import { createProsohmTheme } from './prosohmTheme';

export interface AppThemeOptions {
  mode: 'light' | 'dark';
  branding: BrandingSettings;
  preferences?: Pick<UserPreferences, 'font_size' | 'table_density' | 'animations_enabled' | 'reduced_motion'>;
}

const FONT_SCALE = {
  small: 0.92,
  medium: 1,
  large: 1.08,
} as const;

const DENSITY_SPACING = {
  compact: 6,
  comfortable: 8,
  default: 8,
} as const;

function contrastText(hex: string): string {
  const value = hex.replace('#', '');
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? '#0F172A' : '#FFFFFF';
}

export function createAppTheme({
  mode,
  branding,
  preferences,
}: AppThemeOptions): Theme {
  const base = createProsohmTheme(mode);
  const fontScale = FONT_SCALE[preferences?.font_size ?? 'medium'];
  const spacingUnit = DENSITY_SPACING[preferences?.table_density === 'compact' ? 'compact' : 'default'];
  const radius = branding.border_radius ?? 12;
  const buttonRadius =
    branding.button_style === 'pill' ? 999 : branding.button_style === 'sharp' ? 4 : radius;

  const paletteOverrides: ThemeOptions['palette'] = {
    primary: {
      main: branding.primary_color,
      dark: branding.primary_color,
      contrastText: contrastText(branding.primary_color),
    },
    secondary: {
      main: branding.secondary_color,
      dark: branding.secondary_color,
      contrastText: contrastText(branding.secondary_color),
    },
    success: { main: branding.success_color },
    warning: { main: branding.warning_color },
    error: { main: branding.danger_color },
    accent: {
      main: branding.accent_color,
      dark: branding.accent_color,
      contrastText: contrastText(branding.accent_color),
    },
    prosohm: {
      ...base.palette.prosohm,
      sidebar: branding.sidebar_color,
      sidebarDark: branding.sidebar_color,
      header: branding.header_color,
      accent: branding.accent_color,
      gradientLogin: `linear-gradient(160deg, ${branding.sidebar_color} 0%, ${branding.secondary_color} 55%, ${branding.primary_color} 100%)`,
      gradientSidebar: `linear-gradient(180deg, ${alpha('#FFFFFF', 0.04)} 0%, ${alpha('#000000', 0.08)} 100%)`,
    },
  };

  const cardShadow =
    branding.card_style === 'flat'
      ? 'none'
      : branding.card_style === 'bordered'
        ? 'none'
        : base.palette.prosohm?.shadowCard;

  return createTheme(base, {
    palette: paletteOverrides,
    spacing: spacingUnit,
    shape: { borderRadius: radius },
    typography: {
      fontSize: Math.round(14 * fontScale),
      pageTitle: { ...base.typography.pageTitle, fontSize: `${1.75 * fontScale}rem` },
      sectionTitle: { ...base.typography.sectionTitle, fontSize: `${1.125 * fontScale}rem` },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: buttonRadius,
            transition: preferences?.animations_enabled === false ? 'none' : undefined,
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: radius + 4,
            boxShadow: cardShadow,
            border:
              branding.card_style === 'bordered'
                ? `1px solid ${alpha(branding.secondary_color, 0.18)}`
                : undefined,
          },
        },
      },
      MuiCssBaseline: {
        styleOverrides: {
          '*': preferences?.reduced_motion
            ? {
                animationDuration: '0.01ms !important',
                animationIterationCount: '1 !important',
                transitionDuration: '0.01ms !important',
              }
            : undefined,
        },
      },
    },
  });
}

export function resolveThemeMode(
  preferenceMode: UserPreferences['theme_mode'],
  companyPreset: BrandingSettings,
  systemPrefersDark: boolean,
): 'light' | 'dark' {
  if (preferenceMode === 'light') return 'light';
  if (preferenceMode === 'dark') return 'dark';
  if (preferenceMode === 'system') {
    return systemPrefersDark ? 'dark' : 'light';
  }
  if (companyPreset.theme_preset === 'modern_dark') return 'dark';
  return 'light';
}
