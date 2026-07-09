import type { ListParams } from '../api/client';

export const DEFAULT_PAGE_SIZE = 25;
export const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;
export const PAGE_SIZE_STORAGE_KEY = 'protrack:pagination:page-size';

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  total_records?: number;
  total_pages?: number;
  has_next?: boolean;
  has_previous?: boolean;
}

export interface PaginationParams extends ListParams {
  page?: number;
  page_size?: number;
  skip?: number;
  limit?: number;
  sort?: string;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null;
}

/** Coerce any list API payload into a safe array — never throws. */
export function ensureArray<T>(value: unknown): T[] {
  if (Array.isArray(value)) {
    return value;
  }

  const record = asRecord(value);
  if (!record) {
    return [];
  }

  if (Array.isArray(record.items)) {
    return record.items as T[];
  }
  if (Array.isArray(record.data)) {
    return record.data as T[];
  }
  if (Array.isArray(record.results)) {
    return record.results as T[];
  }

  return [];
}

export function isPaginatedResponse<T>(value: unknown): value is PaginatedResponse<T> {
  const record = asRecord(value);
  if (!record || !Array.isArray(record.items)) {
    return false;
  }

  return (
    typeof record.total === 'number' ||
    typeof record.total_records === 'number'
  );
}

export function unwrapListResponse<T>(value: unknown): T[] {
  return ensureArray<T>(value);
}

export function toSkipLimit(page: number, pageSize: number): { skip: number; limit: number } {
  return {
    skip: (page - 1) * pageSize,
    limit: pageSize,
  };
}

export function clampPage(page: number, total: number, pageSize: number): number {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return Math.min(Math.max(1, page), pages);
}

export function normalizePaginatedResponse<T>(value: unknown): PaginatedResponse<T> {
  if (isPaginatedResponse<T>(value)) {
    const record = value as PaginatedResponse<T>;
    const total = record.total_records ?? record.total ?? record.items.length;
    const pageSize = record.page_size || DEFAULT_PAGE_SIZE;
    const pages =
      record.total_pages ??
      record.pages ??
      Math.max(1, Math.ceil(total / pageSize));
    const page = record.page || 1;

    return {
      items: record.items,
      total,
      page,
      page_size: pageSize,
      pages,
      total_records: total,
      total_pages: pages,
      has_next: record.has_next ?? page < pages,
      has_previous: record.has_previous ?? page > 1,
    };
  }

  const items = ensureArray<T>(value);
  const pageSize = items.length > 0 ? Math.min(items.length, DEFAULT_PAGE_SIZE) : DEFAULT_PAGE_SIZE;

  return {
    items,
    total: items.length,
    page: 1,
    page_size: pageSize,
    pages: 1,
    total_records: items.length,
    total_pages: 1,
    has_next: false,
    has_previous: false,
  };
}
