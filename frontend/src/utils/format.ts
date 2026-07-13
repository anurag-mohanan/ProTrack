import { formatCellValue, formatDisplayValue, isBlankDisplayValue } from './formValues';

export function sanitizeDisplayText(value: unknown): string {
  if (isBlankDisplayValue(value)) {
    return '';
  }
  if (typeof value === 'string') {
    const parts = value.trim().split(/\s+/).filter((part) => !isBlankDisplayValue(part));
    return parts.join(' ');
  }
  return String(value).trim();
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '';
  }
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

/** Indian grouping (lakhs/crores style) for finance plan displays. */
export function formatIndianNumber(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') return '';
  const numeric = Number(String(value).replace(/,/g, ''));
  if (Number.isNaN(numeric)) return String(value);
  return numeric.toLocaleString('en-IN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

export function formatDate(value: string | null | undefined): string {
  if (isBlankDisplayValue(value)) return '';
  const [year, month, day] = value!.split('-').map(Number);
  if (!year || !month || !day) return '';
  return new Date(year, month - 1, day).toLocaleDateString();
}

export function formatDateTime(value: string | null | undefined): string {
  if (isBlankDisplayValue(value)) return '';
  const parsed = new Date(value!);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleString();
}

export function formatStatus(value: string): string {
  if (isBlankDisplayValue(value)) return '';
  return value.replace(/_/g, ' ');
}

export function userDisplayName(user: {
  first_name: string;
  last_name: string;
}): string {
  const name = `${sanitizeDisplayText(user.first_name)} ${sanitizeDisplayText(user.last_name)}`.trim();
  return name || '';
}

export function formatUserWorkload(projectCount: number | null | undefined): string {
  const count = projectCount ?? 0;
  if (count <= 0) return 'Free';
  if (count === 1) return '1 Project';
  return `${count} Projects`;
}

export function formatEmploymentType(value: string | null | undefined): string {
  if (isBlankDisplayValue(value)) return '';
  return formatStatus(value!);
}

export function userInitials(user: {
  first_name: string;
  last_name: string;
}): string {
  const first = user.first_name?.trim()?.[0] ?? '';
  const last = user.last_name?.trim()?.[0] ?? '';
  return `${first}${last}`.toUpperCase() || '?';
}

export { formatCellValue, formatDisplayValue, isBlankDisplayValue };
