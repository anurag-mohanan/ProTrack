import type { DashboardSummary } from '../types';
import { formatNumber } from './format';

export function buildDashboardSummaryLine(summary: DashboardSummary | undefined): string {
  if (!summary) return '';
  const parts = [
    `${formatNumber(summary.active_projects, 0)} Active Projects`,
    `${formatNumber(summary.projects_due_today ?? 0, 0)} Due Today`,
    `${formatNumber((summary.red_projects ?? 0) + (summary.yellow_projects ?? 0), 0)} High Risk`,
    `${formatNumber(summary.designer_availability_summary?.available ?? 0, 0)} Engineers Available`,
    `${formatNumber(summary.overdue_projects ?? 0, 0)} Overdue`,
  ];
  return parts.join(' • ');
}
