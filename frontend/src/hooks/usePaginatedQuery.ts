import { useEffect, useMemo } from 'react';
import { useQuery, type UseQueryOptions } from '@tanstack/react-query';
import type { ListParams } from '../api/client';
import type { PaginatedResponse } from '../types/pagination';
import { usePagination } from './usePagination';

export interface UsePaginatedQueryOptions<T> {
  queryKey: readonly unknown[];
  fetcher: (params: ListParams) => Promise<PaginatedResponse<T>>;
  filters?: ListParams;
  enabled?: boolean;
  staleTime?: number;
  queryOptions?: Omit<
    UseQueryOptions<PaginatedResponse<T>>,
    'queryKey' | 'queryFn' | 'enabled' | 'staleTime'
  >;
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

  const requestParams = useMemo(
    () => ({
      ...pagination.params,
      ...filters,
    }),
    [pagination.params, filters],
  );

  const filterKey = useMemo(() => JSON.stringify(filters), [filters]);

  useEffect(() => {
    pagination.resetPage();
  }, [filterKey, pagination.resetPage]);

  const query = useQuery({
    queryKey: [...queryKey, requestParams],
    queryFn: () => fetcher(requestParams),
    enabled,
    staleTime,
    ...queryOptions,
  });

  useEffect(() => {
    if (query.data) {
      pagination.setTotal(query.data.total_records ?? query.data.total);
    }
  }, [query.data, pagination.setTotal]);

  return {
    pagination,
    query,
    items: query.data?.items ?? [],
    data: query.data,
  };
}
