import type { ComponentProps } from 'react';
import type { GridValidRowModel } from '@mui/x-data-grid';
import { ensureArray } from '../../types/pagination';
import { ProsohmDataGrid } from '../ui/design-system/ProsohmDataGrid';
import { ProTrackPagination } from './ProTrackPagination';
import type { UsePaginationResult } from '../../hooks/usePagination';

type ProsohmDataGridProps<R extends GridValidRowModel> = ComponentProps<typeof ProsohmDataGrid<R>>;

interface PaginatedDataGridProps<R extends GridValidRowModel = GridValidRowModel>
  extends Omit<ProsohmDataGridProps<R>, 'pagination' | 'paginationMode' | 'paginationModel' | 'rowCount'> {
  pagination: UsePaginationResult;
  loading?: boolean;
  paginationLabel?: string;
}

export function PaginatedDataGrid<R extends GridValidRowModel = GridValidRowModel>({
  pagination,
  loading = false,
  paginationLabel = 'records',
  rows,
  ...gridProps
}: PaginatedDataGridProps<R>) {
  const safeRows = ensureArray<R>(rows);

  return (
    <>
      <ProsohmDataGrid
        {...gridProps}
        rows={safeRows}
        loading={loading}
        hideFooter
      />
      <ProTrackPagination
        page={pagination.page}
        pageSize={pagination.pageSize}
        total={pagination.total}
        pages={pagination.pages}
        rangeStart={pagination.rangeStart}
        rangeEnd={pagination.rangeEnd}
        loading={loading}
        pageSizeOptions={pagination.pageSizeOptions}
        onPageChange={pagination.goToPage}
        onPageSizeChange={pagination.setPageSize}
        label={paginationLabel}
      />
    </>
  );
}
