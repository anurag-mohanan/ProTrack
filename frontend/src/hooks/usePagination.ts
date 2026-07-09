import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ListParams } from '../api/client';
import {
  clampPage,
  DEFAULT_PAGE_SIZE,
  PAGE_SIZE_OPTIONS,
  PAGE_SIZE_STORAGE_KEY,
} from '../types/pagination';

export interface UsePaginationOptions {
  storageKey?: string;
  defaultPageSize?: number;
  pageSizeOptions?: readonly number[];
  total?: number;
  initialPage?: number;
}

export interface UsePaginationResult {
  page: number;
  pageSize: number;
  pageSizeOptions: readonly number[];
  total: number;
  pages: number;
  params: ListParams;
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
  resetPage: () => void;
  setTotal: (total: number) => void;
  goToPage: (page: number) => void;
  nextPage: () => void;
  previousPage: () => void;
  firstPage: () => void;
  lastPage: () => void;
  rangeStart: number;
  rangeEnd: number;
  hasNext: boolean;
  hasPrevious: boolean;
}

function readStoredPageSize(storageKey: string, fallback: number): number {
  if (typeof window === 'undefined') return fallback;
  const stored = Number(window.localStorage.getItem(storageKey) ?? 0);
  return PAGE_SIZE_OPTIONS.includes(stored as (typeof PAGE_SIZE_OPTIONS)[number])
    ? stored
    : fallback;
}

function computePages(total: number, pageSize: number): number {
  if (total <= 0) return 1;
  return Math.max(1, Math.ceil(total / pageSize));
}

export function usePagination({
  storageKey = PAGE_SIZE_STORAGE_KEY,
  defaultPageSize = DEFAULT_PAGE_SIZE,
  pageSizeOptions = PAGE_SIZE_OPTIONS,
  total = 0,
  initialPage = 1,
}: UsePaginationOptions = {}): UsePaginationResult {
  const [page, setPageState] = useState(initialPage);
  const [pageSize, setPageSizeState] = useState(() =>
    readStoredPageSize(storageKey, defaultPageSize),
  );
  const [totalCount, setTotalCount] = useState(total);

  const totalRef = useRef(totalCount);
  const pageSizeRef = useRef(pageSize);
  totalRef.current = totalCount;
  pageSizeRef.current = pageSize;

  useEffect(() => {
    setTotalCount(total);
  }, [total]);

  const pages = useMemo(
    () => computePages(totalCount, pageSize),
    [totalCount, pageSize],
  );

  // When the dataset shrinks, clamp the current page — never reset on unrelated updates.
  useEffect(() => {
    if (totalCount <= 0) return;
    setPageState((current) => clampPage(current, totalCount, pageSize));
  }, [totalCount, pageSize]);

  const setPage = useCallback((nextPage: number) => {
    setPageState(Math.max(1, nextPage));
  }, []);

  const setPageSize = useCallback(
    (nextPageSize: number) => {
      setPageSizeState(nextPageSize);
      setPageState(1);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(storageKey, String(nextPageSize));
      }
    },
    [storageKey],
  );

  const resetPage = useCallback(() => setPageState(1), []);

  const goToPage = useCallback((target: number) => {
    setPageState((current) => {
      const totalValue = totalRef.current;
      const size = pageSizeRef.current;
      const safeTarget = Math.max(1, Math.floor(target));

      if (totalValue <= 0) {
        // Allow navigation while total is still loading; clamp once total arrives.
        return Math.max(1, safeTarget);
      }

      return clampPage(safeTarget, totalValue, size);
    });
  }, []);

  const nextPage = useCallback(() => {
    setPageState((current) => {
      const totalValue = totalRef.current;
      const size = pageSizeRef.current;
      const maxPage = computePages(totalValue, size);
      return Math.min(maxPage, current + 1);
    });
  }, []);

  const previousPage = useCallback(() => {
    setPageState((current) => Math.max(1, current - 1));
  }, []);

  const firstPage = useCallback(() => setPageState(1), []);

  const lastPage = useCallback(() => {
    setPageState(() => {
      const totalValue = totalRef.current;
      const size = pageSizeRef.current;
      return computePages(totalValue, size);
    });
  }, []);

  const rangeStart = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = totalCount === 0 ? 0 : Math.min(page * pageSize, totalCount);

  const params = useMemo<ListParams>(
    () => ({
      page,
      page_size: pageSize,
      skip: (page - 1) * pageSize,
      limit: pageSize,
    }),
    [page, pageSize],
  );

  return {
    page,
    pageSize,
    pageSizeOptions,
    total: totalCount,
    pages,
    params,
    setPage,
    setPageSize,
    resetPage,
    setTotal: setTotalCount,
    goToPage,
    nextPage,
    previousPage,
    firstPage,
    lastPage,
    rangeStart,
    rangeEnd,
    hasNext: totalCount > 0 ? page < pages : false,
    hasPrevious: page > 1,
  };
}
