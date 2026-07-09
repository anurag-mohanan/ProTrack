import { useEffect, useMemo } from 'react';
import { keepPreviousData, useQuery, type UseQueryOptions } from '@tanstack/react-query';
import type { ListParams } from '../api/client';
import { ensureArray, type PaginatedResponse } from '../types/pagination';
import { usePagination } from './usePagination';

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
      skip: (pagination.page - 1) * pagination.pageSize,
      limit: pagination.pageSize,
      ...filters,
    }),
    [pagination.page, pagination.pageSize, filterKey, filters],
  );

  const requestKey = useMemo(
    () => serializeParams(requestParams),
    [requestParams],
  );

  // Reset to page 1 only when filters/search change — never when page changes.
  useEffect(() => {
    pagination.resetPage();
  }, [filterKey, pagination.resetPage]);

  const query = useQuery({
    queryKey: [...queryKey, requestKey],
    queryFn: () => fetcher(requestParams),
    enabled,
    staleTime,
    placeholderData: keepPreviousData,
    ...queryOptions,
  });

  useEffect(() => {
    if (query.data) {
      pagination.setTotal(query.data.total_records ?? query.data.total ?? 0);
    }
  }, [query.data, pagination.setTotal]);

  const items = useMemo(() => {
    if (!query.data) return [];
    // Avoid showing rows from a previous page while the next page is loading.
    if (query.isFetching && query.data.page !== pagination.page) {
      return [];
    }
    return ensureArray<T>(query.data.items);
  }, [query.data, query.isFetching, pagination.page]);

  return {
    pagination,
    query,
    items,
    data: query.data,
    requestParams,
  };
}
