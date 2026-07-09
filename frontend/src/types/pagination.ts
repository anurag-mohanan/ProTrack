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
}

export interface PaginationParams extends ListParams {
  page?: number;
  page_size?: number;
  skip?: number;
  limit?: number;
  sort?: string;
}

export function isPaginatedResponse<T>(value: unknown): value is PaginatedResponse<T> {
  return (
    typeof value === 'object' &&
    value !== null &&
    'items' in value &&
    Array.isArray((value as PaginatedResponse<T>).items) &&
    'total' in value
  );
}

export function unwrapListResponse<T>(value: T[] | PaginatedResponse<T>): T[] {
  if (isPaginatedResponse<T>(value)) {
    return value.items;
  }
  return value;
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
