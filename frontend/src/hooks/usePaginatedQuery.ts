import { useEffect, useMemo } from 'react';
import { keepPreviousData, useQuery, type UseQueryOptions } from '@tanstack/react-query';
import type { ListParams } from '../api/client';
import { ensureArray, type PaginatedResponse } from '../types/pagination';
import { usePagination } from './usePagination';
import { useResetPageOnFilterChange } from './useResetPageOnFilterChange';

export interface UsePaginatedQueryOptions<T> {
  queryKey: readonly unknown[];
  fetcher: (params: ListParams) => Promise<PaginatedResponse<T>>;
  filters?: ListParams;
  enabled?: boolean;
  staleTime?: number;
  queryOptions?: Omit<
    UseQueryOptions<PaginatedResponse<T>>,
    'queryKey' | 'queryFn' | 'enabled' | 'staleTime' | 'placeholderData'
  >;
}

function serializeParams(params: ListParams): string {
  const entries = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== '')
    .sort(([left], [right]) => left.localeCompare(right));
  return JSON.stringify(entries);
}

export function usePaginatedQuery<T>({
  queryKey,
  fetcher,
  filters = {},
  enabled = true,
  staleTime,
  queryOptions,
}: UsePaginatedQueryOptions<T>) {
  const pagination = usePagination();

  const filterKey = useMemo(() => serializeParams(filters), [filters]);

  const requestParams = useMemo(
    () => ({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters,
    }),
    [pagination.page, pagination.pageSize, filterKey, filters],
  );

  const requestKey = useMemo(
    () => serializeParams(requestParams),
    [requestParams],
  );

  useResetPageOnFilterChange(filterKey, pagination.resetPage);

  const query = useQuery({
    queryKey: [...queryKey, requestKey],
    queryFn: () => fetcher(requestParams),
    enabled,
    staleTime,
    placeholderData: keepPreviousData,
    ...queryOptions,
  });

  // Only apply totals from the latest fetched page — never from stale placeholder data.
  useEffect(() => {
    if (!query.data || query.isPlaceholderData) {
      return;
    }
    pagination.setTotal(query.data.total_records ?? query.data.total ?? 0);
  }, [query.data, query.isPlaceholderData, pagination.setTotal]);

  const items = useMemo(() => {
    if (!query.data) return [];
    return ensureArray<T>(query.data.items);
  }, [query.data]);

  const isEmpty = items.length === 0 && !query.isFetching && !query.isLoading;
  const isPageTransitioning =
    query.isFetching && query.data != null && query.data.page !== pagination.page;

  return {
    pagination,
    query,
    items,
    data: query.data,
    requestParams,
    isEmpty,
    isPageTransitioning,
  };
}
