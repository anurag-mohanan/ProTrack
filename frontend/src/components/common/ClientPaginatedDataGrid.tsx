import { useEffect, useMemo, type ComponentProps } from 'react';
import type { GridValidRowModel } from '@mui/x-data-grid';
import { ensureArray } from '../../types/pagination';
import { usePagination } from '../../hooks/usePagination';
import { PaginatedDataGrid } from './PaginatedDataGrid';

type PaginatedDataGridProps<R extends GridValidRowModel> = ComponentProps<
  typeof PaginatedDataGrid<R>
>;

export interface ClientPaginatedDataGridProps<R extends GridValidRowModel = GridValidRowModel>
  extends Omit<PaginatedDataGridProps<R>, 'pagination' | 'rows'> {
  rows: unknown;
  /** Reset to page 1 when filters/search change. */
  filterKey?: string | number;
}

export function ClientPaginatedDataGrid<R extends GridValidRowModel = GridValidRowModel>({
  rows,
  filterKey,
  ...gridProps
}: ClientPaginatedDataGridProps<R>) {
  const pagination = usePagination();
  const safeRows = useMemo(() => ensureArray<R>(rows), [rows]);

  useEffect(() => {
    pagination.setTotal(safeRows.length);
  }, [safeRows.length, pagination.setTotal]);

  useEffect(() => {
    pagination.resetPage();
  }, [filterKey, pagination.resetPage]);

  const pagedRows = useMemo(() => {
    const start = (pagination.page - 1) * pagination.pageSize;
    return safeRows.slice(start, start + pagination.pageSize);
  }, [safeRows, pagination.page, pagination.pageSize]);

  return (
    <PaginatedDataGrid
      {...gridProps}
      rows={pagedRows}
      pagination={pagination}
    />
  );
}
