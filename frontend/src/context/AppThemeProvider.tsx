import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchMyPreferences } from '../api/preferences';
import { fetchPublicSettings } from '../api/settings';
import { CompanyProvider } from './CompanyContext';
import { PreferencesProvider } from './PreferencesContext';
import { useAuth } from './AuthContext';
import { createAppTheme, resolveThemeMode } from '../theme/createAppTheme';
import { DEFAULT_USER_PREFERENCES } from '../types/Preferences';
import type { BrandingSettings } from '../types/Settings';
import { getPresetById } from '../theme/brandingPresets';

const FALLBACK_BRANDING: BrandingSettings = {
  id: 'default',
  ...getPresetById('prosohm_professional').colors,
  theme_preset: 'prosohm_professional',
  button_style: 'rounded',
  border_radius: 12,
  card_style: 'elevated',
  density: 'default',
};

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [systemDark, setSystemDark] = useState(
    () => window.matchMedia('(prefers-color-scheme: dark)').matches,
  );

  const publicQuery = useQuery({
    queryKey: ['settings', 'public'],
    queryFn: fetchPublicSettings,
    staleTime: 5 * 60 * 1000,
  });

  const preferencesQuery = useQuery({
    queryKey: ['preferences', 'me'],
    queryFn: fetchMyPreferences,
    enabled: Boolean(user),
    staleTime: 60 * 1000,
  });

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    media.addEventListener('change', handler);
    return () => media.removeEventListener('change', handler);
  }, []);

  const branding = publicQuery.data?.branding ?? FALLBACK_BRANDING;
  const company = publicQuery.data?.company ?? null;
  const preferences = preferencesQuery.data ?? {
    id: 'local',
    user_id: user?.id ?? 'local',
    ...DEFAULT_USER_PREFERENCES,
  };

  const mode = resolveThemeMode(preferences.theme_mode, branding, systemDark);
  const theme = useMemo(
    () =>
      createAppTheme({
        mode,
        branding,
        preferences,
      }),
    [mode, branding, preferences],
  );

  const appName = company?.company_short_name || company?.company_name || 'ProTrack';

  useEffect(() => {
    document.title = `${appName} · ProTrack`;
  }, [appName]);

  return (
    <CompanyProvider
      value={{
        company,
        branding,
        appName,
        isLoading: publicQuery.isLoading,
      }}
    >
      <PreferencesProvider
        value={{
          preferences: user ? preferences : null,
          updatePreferences: async (patch) => {
            if (!user) return;
            const { updateMyPreferences } = await import('../api/preferences');
            await updateMyPreferences(patch);
            await queryClient.invalidateQueries({ queryKey: ['preferences', 'me'] });
          },
          isLoading: user ? preferencesQuery.isLoading : false,
        }}
      >
        <ThemeProvider theme={theme}>
          <CssBaseline />
          {children}
        </ThemeProvider>
      </PreferencesProvider>
    </CompanyProvider>
  );
}
