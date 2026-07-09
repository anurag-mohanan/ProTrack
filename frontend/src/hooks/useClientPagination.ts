import { useEffect, useMemo } from 'react';
import { usePagination, type UsePaginationOptions } from './usePagination';

export function useClientPagination<T>(
  rows: T[],
  options?: Omit<UsePaginationOptions, 'total'>,
) {
  const pagination = usePagination(options);

  useEffect(() => {
    pagination.setTotal(rows.length);
  }, [rows.length, pagination.setTotal]);

  const pagedRows = useMemo(() => {
    const start = (pagination.page - 1) * pagination.pageSize;
    return rows.slice(start, start + pagination.pageSize);
  }, [rows, pagination.page, pagination.pageSize]);

  return {
    pagination,
    pagedRows,
  };
}
