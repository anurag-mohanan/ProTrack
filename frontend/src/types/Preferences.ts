export type ThemeModePreference = 'company_default' | 'system' | 'light' | 'dark';
export type DashboardLayoutPreference = 'compact' | 'comfortable' | 'default';
export type TableDensityPreference = 'compact' | 'comfortable';
export type FontSizePreference = 'small' | 'medium' | 'large';
export type LandingPagePreference = 'dashboard' | 'projects' | 'timesheets' | 'admin';
export type ProjectsPortfolioScopePreference = 'my_streams' | 'my_teams' | 'all';
export type ProjectsCcLayoutPreference = 'list' | 'card' | 'grouped';

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
  projects_portfolio_scope?: ProjectsPortfolioScopePreference;
  projects_cc_layout?: ProjectsCcLayoutPreference;
  projects_cc_default_view_id?: string | null;
  projects_cc_show_workstreams?: boolean;
  projects_cc_show_teams?: boolean;
  projects_cc_show_status?: boolean;
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
  projects_portfolio_scope: 'my_streams',
  projects_cc_layout: 'grouped',
  projects_cc_show_workstreams: true,
  projects_cc_show_teams: true,
  projects_cc_show_status: true,
};
