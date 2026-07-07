import type { DashboardSummary } from '../types';
import { hoursBurnPercent } from './projectHoursMetrics';

export const STABLE_TREND = { value: 'Stable', direction: 'flat' as const };

export function activeCustomerCount(summary: DashboardSummary | undefined): number {
  return (summary?.customer_workload ?? []).filter((row) => row.active_tools > 0).length;
}

export function hoursUtilizationPercent(summary: DashboardSummary | undefined): number {
  const quoted = Number(summary?.total_quoted_hours_active ?? 0);
  const actual = Number(summary?.total_actual_hours_productive ?? 0);
  return Math.round(hoursBurnPercent(actual, quoted));
}

export function designerUtilizationPercent(summary: DashboardSummary | undefined): number {
  const stats = summary?.designer_availability_summary;
  if (!stats?.total_designers) return 0;
  return Math.round((stats.allocated / stats.total_designers) * 100);
}

export function surfacerUtilizationPercent(summary: DashboardSummary | undefined): number {
  const rows = summary?.designer_availability ?? [];
  if (!rows.length) return 0;
  const busy = rows.filter((row) => row.status === 'working' || row.status === 'on_hold').length;
  return Math.round((busy / rows.length) * 100);
}

export function availableCapacityHours(summary: DashboardSummary | undefined): number {
  return (summary?.team_summary ?? []).reduce(
    (sum, row) => sum + Number(row.available_capacity_hours ?? 0),
    0,
  );
}

export function averageHoursPerProject(summary: DashboardSummary | undefined): number {
  const active = Math.max(1, summary?.active_projects ?? 0);
  return Number(summary?.total_actual_hours_productive ?? 0) / active;
}

export function teamProductivityPercent(summary: DashboardSummary | undefined): number {
  return Math.round(Number(summary?.productive_percent ?? 0));
}
