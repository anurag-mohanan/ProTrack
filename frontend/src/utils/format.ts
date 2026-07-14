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

/** Coerce API Decimal/string/number payloads to a finite number (else 0). */
export function toFiniteNumber(value: unknown): number {
  if (value === null || value === undefined || value === '') return 0;
  const n = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  return Number.isFinite(n) ? n : 0;
}

export function formatNumber(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') {
    return '';
  }
  const n = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  if (!Number.isFinite(n)) {
    return '';
  }
  return n.toLocaleString(undefined, {
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

/** Canonical calendar-date display across ProTrack: DD-MM-YYYY. */
export function formatDate(value: string | null | undefined): string {
  if (isBlankDisplayValue(value)) return '';
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return '';
  const [, year, month, day] = match;
  return `${day}-${month}-${year}`;
}

/** Canonical datetime display: DD-MM-YYYY HH:mm (local). */
export function formatDateTime(value: string | null | undefined): string {
  if (isBlankDisplayValue(value)) return '';
  const parsed = new Date(value!);
  if (Number.isNaN(parsed.getTime())) return '';
  const date = formatDate(
    `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}-${String(parsed.getDate()).padStart(2, '0')}`,
  );
  const time = `${String(parsed.getHours()).padStart(2, '0')}:${String(parsed.getMinutes()).padStart(2, '0')}`;
  return date ? `${date} ${time}` : '';
}

/**
 * On-time when completion calendar day is on or before the target due date.
 * Returns null when not evaluable (not completed, or missing dates).
 */
export function isCompletedOnTime(args: {
  status: string;
  dueDate?: string | null;
  completedDate?: string | null;
  completedAt?: string | null;
}): boolean | null {
  if (args.status !== 'completed') return null;
  const dueMatch = args.dueDate ? String(args.dueDate).match(/^(\d{4})-(\d{2})-(\d{2})/) : null;
  const completedRaw = args.completedDate ?? args.completedAt ?? null;
  const completedMatch = completedRaw
    ? String(completedRaw).match(/^(\d{4})-(\d{2})-(\d{2})/)
    : null;
  if (!dueMatch || !completedMatch) return null;
  const dueKey = `${dueMatch[1]}${dueMatch[2]}${dueMatch[3]}`;
  const completedKey = `${completedMatch[1]}${completedMatch[2]}${completedMatch[3]}`;
  return completedKey <= dueKey;
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
