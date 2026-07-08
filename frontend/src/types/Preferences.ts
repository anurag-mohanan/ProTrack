export type ThemeModePreference = 'company_default' | 'system' | 'light' | 'dark';
export type DashboardLayoutPreference = 'compact' | 'comfortable' | 'default';
export type TableDensityPreference = 'compact' | 'comfortable';
export type FontSizePreference = 'small' | 'medium' | 'large';
export type LandingPagePreference = 'dashboard' | 'projects' | 'timesheets' | 'admin';

export interface UserPreferences {
  id: string;
  user_id: string;
  theme_mode: ThemeModePreference;
  sidebar_expanded: boolean;
  sidebar_auto_collapse: boolean;
  dashboard_layout: DashboardLayoutPreference;
  table_density: TableDensityPreference;
  font_size: FontSizePreference;
  animations_enabled: boolean;
  reduced_motion: boolean;
  default_landing_page: LandingPagePreference;
  email_notifications_enabled?: boolean;
  created_at?: string;
  updated_at?: string;
}

export const DEFAULT_USER_PREFERENCES: Omit<UserPreferences, 'id' | 'user_id'> = {
  theme_mode: 'company_default',
  sidebar_expanded: true,
  sidebar_auto_collapse: false,
  dashboard_layout: 'default',
  table_density: 'comfortable',
  font_size: 'medium',
  animations_enabled: true,
  reduced_motion: false,
  default_landing_page: 'dashboard',
};
