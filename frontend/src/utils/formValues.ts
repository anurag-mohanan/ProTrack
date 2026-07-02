const INVALID_DISPLAY_VALUES = new Set([
  '#value',
  '#value!',
  '#n/a',
  '#ref!',
  '#name?',
  '#div/0!',
  '#null!',
  '#num!',
  'undefined',
  'null',
  'nan',
  '[object object]',
]);

export function isBlankDisplayValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return true;
  }
  if (typeof value === 'number' && Number.isNaN(value)) {
    return true;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) {
      return true;
    }
    return INVALID_DISPLAY_VALUES.has(trimmed.toLowerCase());
  }
  return false;
}

/** Display empty cells/fields as blank instead of placeholders like #VALUE. */
export function formatCellValue(value: unknown): string {
  if (isBlankDisplayValue(value)) {
    return '';
  }
  if (typeof value === 'string') {
    return value.trim();
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return '';
}

/** Display value or em dash for empty/invalid cells. */
export function formatDisplayValue(value: unknown, fallback = '—'): string {
  const formatted = formatCellValue(value);
  return formatted || fallback;
}

export function optionalString(value: string | null | undefined): string | null {
  if (isBlankDisplayValue(value)) {
    return null;
  }
  return String(value).trim();
}

export function optionalUuid(value: string | null | undefined): string | null {
  const cleaned = optionalString(value);
  return cleaned || null;
}

export function optionalNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function validateRequiredFields(
  values: object,
  fields: Array<{ key: string; label: string }>,
): string | null {
  const record = values as Record<string, unknown>;
  for (const field of fields) {
    if (isBlankDisplayValue(record[field.key])) {
      return `${field.label} is required.`;
    }
  }
  return null;
}
