import type { CustomerTimesheetPackPayload } from '../types/CustomerTimesheetPack';
import { apiClient, buildQuery, API_BASE_URL } from './client';
import { getAccessToken } from '../services/authStorage';

export interface CustomerTimesheetPackOptions {
  customer_id: string;
  period_type?: 'weekly' | 'monthly';
  anchor?: string;
  team_id?: string;
}

function packQuery(options: CustomerTimesheetPackOptions): string {
  return buildQuery({
    customer_id: options.customer_id,
    period_type: options.period_type,
    anchor: options.anchor,
    team_id: options.team_id,
  });
}

export async function fetchCustomerTimesheetPackPreview(
  options: CustomerTimesheetPackOptions,
): Promise<CustomerTimesheetPackPayload> {
  const { data } = await apiClient.get<CustomerTimesheetPackPayload>(
    `/reports/customer-timesheet-pack/preview${packQuery(options)}`,
  );
  return data;
}

export async function downloadCustomerTimesheetPackExcel(
  options: CustomerTimesheetPackOptions,
): Promise<void> {
  const token = getAccessToken();
  const response = await fetch(
    `${API_BASE_URL}/reports/customer-timesheet-pack/export.xlsx${packQuery(options)}`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  );
  if (!response.ok) {
    throw new Error('Failed to download customer timesheet pack.');
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? 'customer-timesheet-pack.xlsx';
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export const customerTimesheetPackQueryKeys = {
  preview: (options: CustomerTimesheetPackOptions) =>
    ['customer-timesheet-pack', 'preview', options] as const,
};
