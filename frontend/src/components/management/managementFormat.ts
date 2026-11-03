import type { ReactNode } from 'react';
import type { CustomerRow, MetricUnit } from '../../types/Management';
import { formatNumber } from '../../utils/format';

export const PRINCIPLE =
  'Actuals, approved plans, forecasts and targets are labelled separately and never combined.';

export interface Column<T> {
  label: string;
  render: (row: T) => ReactNode;
  align?: 'left' | 'right';
}

export function valueText(value: number | null | undefined, unit: MetricUnit | string): string {
  if (value === null || value === undefined) return '—';
  switch (unit) {
    case 'currency':
      return `INR ${formatNumber(value, 0)}`;
    case 'percentage':
      return `${formatNumber(value, 1)}%`;
    case 'hours':
      return `${formatNumber(value, 1)} h`;
    case 'days':
      return `${formatNumber(value, 1)} days`;
    case 'ratio':
      return formatNumber(value, 2);
    default:
      return formatNumber(value, 0);
  }
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return '—';
  return status.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

export function customerColumns(financeVisible: boolean): Column<CustomerRow>[] {
  const base: Column<CustomerRow>[] = [
    { label: 'Customer', render: (r) => r.customer },
    { label: 'Projects', align: 'right', render: (r) => r.projects },
    { label: 'Active', align: 'right', render: (r) => r.active_projects },
    { label: 'Completed in period', align: 'right', render: (r) => r.completed_in_period },
    { label: 'On-time', align: 'right', render: (r) => valueText(r.on_time_rate, 'percentage') },
    { label: 'Hour variance', align: 'right', render: (r) => valueText(r.hour_variance_percent, 'percentage') },
  ];
  if (!financeVisible) return base;
  return [
    ...base,
    { label: 'Invoiced', align: 'right', render: (r) => valueText(r.invoiced, 'currency') },
    { label: 'Trend', align: 'right', render: (r) => valueText(r.revenue_trend_percent, 'percentage') },
    { label: 'Collected', align: 'right', render: (r) => valueText(r.collected, 'currency') },
    { label: 'Outstanding', align: 'right', render: (r) => valueText(r.outstanding, 'currency') },
  ];
}
