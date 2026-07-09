import type { ComponentProps } from 'react';
import type { GridValidRowModel } from '@mui/x-data-grid';
import type { ListParams } from '../../api/client';
import type { PaginatedResponse } from '../../types/pagination';
import { usePaginatedQuery } from '../../hooks/usePaginatedQuery';
import { PaginatedDataGrid } from './PaginatedDataGrid';

type PaginatedDataGridProps<R extends GridValidRowModel> = ComponentProps<
  typeof PaginatedDataGrid<R>
>;

export interface ServerPaginatedDataGridProps<T, R extends GridValidRowModel = GridValidRowModel>
  extends Omit<PaginatedDataGridProps<R>, 'pagination' | 'rows' | 'loading'> {
  queryKey: readonly unknown[];
  fetcher: (params: ListParams) => Promise<PaginatedResponse<T>>;
  filters?: ListParams;
  enabled?: boolean;
  staleTime?: number;
  /** Map API items to grid rows (defaults to identity). */
  mapRows?: (items: T[]) => R[];
}

/**
 * Standard server-paginated list grid.
 * All server-side admin lists should use this instead of wiring usePaginatedQuery manually.
 */
export function ServerPaginatedDataGrid<T, R extends GridValidRowModel = GridValidRowModel>({
  queryKey,
  fetcher,
  filters,
  enabled,
  staleTime,
  mapRows,
  ...gridProps
}: ServerPaginatedDataGridProps<T, R>) {
  const { pagination, query, items } = usePaginatedQuery<T>({
    queryKey,
    fetcher,
    filters,
    enabled,
    staleTime,
  });

  const rows = mapRows ? mapRows(items) : (items as unknown as R[]);

  return (
    <PaginatedDataGrid
      {...gridProps}
      rows={rows}
      pagination={pagination}
      loading={query.isFetching}
    />
  );
}
