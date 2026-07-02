import type { BrandingSettings, ThemePresetId } from '../types/Settings';

export interface BrandingPreset {
  id: ThemePresetId;
  label: string;
  description: string;
  colors: Omit<
    BrandingSettings,
    'id' | 'theme_preset' | 'button_style' | 'border_radius' | 'card_style' | 'density'
  >;
}

export const BRANDING_PRESETS: BrandingPreset[] = [
  {
    id: 'prosohm_professional',
    label: 'Prosohm Professional',
    description: 'Default engineering workspace palette.',
    colors: {
      primary_color: '#0066B3',
      secondary_color: '#1E293B',
      accent_color: '#0EA5E9',
      success_color: '#16A34A',
      warning_color: '#D97706',
      danger_color: '#DC2626',
      sidebar_color: '#0F172A',
      header_color: '#FFFFFF',
    },
  },
  {
    id: 'modern_light',
    label: 'Modern Light',
    description: 'Bright, airy interface with soft contrast.',
    colors: {
      primary_color: '#2563EB',
      secondary_color: '#475569',
      accent_color: '#6366F1',
      success_color: '#059669',
      warning_color: '#CA8A04',
      danger_color: '#E11D48',
      sidebar_color: '#F8FAFC',
      header_color: '#FFFFFF',
    },
  },
  {
    id: 'modern_dark',
    label: 'Modern Dark',
    description: 'Low-glare dark workspace.',
    colors: {
      primary_color: '#38BDF8',
      secondary_color: '#94A3B8',
      accent_color: '#818CF8',
      success_color: '#34D399',
      warning_color: '#FBBF24',
      danger_color: '#F87171',
      sidebar_color: '#0B1220',
      header_color: '#111827',
    },
  },
  {
    id: 'ocean_blue',
    label: 'Ocean Blue',
    description: 'Cool blues for focused engineering work.',
    colors: {
      primary_color: '#0284C7',
      secondary_color: '#155E75',
      accent_color: '#22D3EE',
      success_color: '#10B981',
      warning_color: '#F59E0B',
      danger_color: '#EF4444',
      sidebar_color: '#082F49',
      header_color: '#F0F9FF',
    },
  },
  {
    id: 'slate_grey',
    label: 'Slate Grey',
    description: 'Neutral enterprise styling.',
    colors: {
      primary_color: '#334155',
      secondary_color: '#64748B',
      accent_color: '#0EA5E9',
      success_color: '#15803D',
      warning_color: '#B45309',
      danger_color: '#B91C1C',
      sidebar_color: '#1E293B',
      header_color: '#F8FAFC',
    },
  },
  {
    id: 'emerald',
    label: 'Emerald',
    description: 'Fresh green accents with professional contrast.',
    colors: {
      primary_color: '#059669',
      secondary_color: '#14532D',
      accent_color: '#14B8A6',
      success_color: '#16A34A',
      warning_color: '#D97706',
      danger_color: '#DC2626',
      sidebar_color: '#052E16',
      header_color: '#ECFDF5',
    },
  },
  {
    id: 'high_contrast',
    label: 'High Contrast',
    description: 'Maximum readability and accessibility.',
    colors: {
      primary_color: '#000000',
      secondary_color: '#111827',
      accent_color: '#2563EB',
      success_color: '#166534',
      warning_color: '#92400E',
      danger_color: '#991B1B',
      sidebar_color: '#000000',
      header_color: '#FFFFFF',
    },
  },
];

export function getPresetById(id: ThemePresetId): BrandingPreset {
  return BRANDING_PRESETS.find((preset) => preset.id === id) ?? BRANDING_PRESETS[0];
}
