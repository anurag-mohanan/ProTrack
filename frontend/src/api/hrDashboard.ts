import { apiClient } from './client';

export type HrDashboardFilters = {
  start_date?: string;
  end_date?: string;
  org_department_id?: string;
  designation?: string;
  manager_id?: string;
  shift_id?: string;
  employment_type?: string;
  status?: 'active' | 'inactive' | 'all';
};

export type HrBreakdownRow = { key: string; label: string; count: number; segment: string };

export type HrTrendRow = {
  month: string;
  label: string;
  opening: number;
  joiners: number;
  exits: number;
  closing: number;
  joiners_segment: string;
  exits_segment: string;
};

export type HrJoinerRow = {
  user_id: string;
  name: string;
  designation: string | null;
  department: string | null;
  manager: string | null;
  joining_date: string | null;
  shift: string | null;
  onboarding: {
    checklist_id: string;
    status: string;
    percent_complete: number;
    pending_items: number;
    overdue: boolean;
  } | null;
  it: {
    request_id: string | null;
    status: string | null;
    required_by: string | null;
    overdue: boolean;
    seat_code: string | null;
  } | null;
};

export type HrAction = {
  code: string;
  title: string;
  severity: 'high' | 'medium' | 'low';
  count: number;
  segment: string;
  module_link: string | null;
};

export type HrOption = { value: string; label: string };

export type HrDashboardOverview = {
  as_of: string;
  period_start: string;
  period_end: string;
  horizon_days: number;
  status: string;
  cards: {
    total_employees: number;
    active_employees: number;
    new_joiners: number;
    upcoming_joiners: number;
    exits: number;
    upcoming_exits: number;
    open_hr_actions: number;
    onboarding_in_progress: number;
    onboarding_overdue: number;
  };
  breakdowns: Record<'department' | 'designation' | 'employment_type' | 'shift' | 'manager', HrBreakdownRow[]>;
  trend: HrTrendRow[];
  tenure: HrBreakdownRow[];
  joiners: HrJoinerRow[];
  performance: {
    review_year: number;
    review_year_label: string;
    sheets: number;
    stages: HrBreakdownRow[];
    overdue: number;
    missing: number;
  };
  milestones: { user_id: string; name: string; date: string; years: number; kind: string }[];
  actions: HrAction[];
  filter_options: {
    departments: HrOption[];
    designations: HrOption[];
    managers: HrOption[];
    shifts: HrOption[];
    employment_types: HrOption[];
  };
};

export type HrSegmentEmployee = {
  user_id: string;
  name: string;
  email: string;
  designation: string | null;
  department: string | null;
  manager: string | null;
  employment_type: string | null;
  joining_date: string | null;
  leaving_date: string | null;
  status: 'active' | 'inactive';
  shift: string | null;
};

function cleanParams(filters: HrDashboardFilters): Record<string, string> {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== ''),
  ) as Record<string, string>;
}

export const hrDashboardKeys = {
  all: ['hr-dashboard'] as const,
  overview: (filters: HrDashboardFilters) => [...hrDashboardKeys.all, 'overview', filters] as const,
  segment: (segment: string, filters: HrDashboardFilters) =>
    [...hrDashboardKeys.all, 'segment', segment, filters] as const,
};

export async function fetchHrDashboardOverview(
  filters: HrDashboardFilters,
): Promise<HrDashboardOverview> {
  const { data } = await apiClient.get<HrDashboardOverview>('/hr/dashboard/overview', {
    params: cleanParams(filters),
  });
  return data;
}

export async function fetchHrSegmentEmployees(
  segment: string,
  filters: HrDashboardFilters,
): Promise<HrSegmentEmployee[]> {
  const { data } = await apiClient.get<HrSegmentEmployee[]>('/hr/dashboard/employees', {
    params: { ...cleanParams(filters), segment },
  });
  return data;
}
