import type { ComponentProps } from 'react';
import type { GridValidRowModel } from '@mui/x-data-grid';
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
  ...gridProps
}: PaginatedDataGridProps<R>) {
  return (
    <>
      <ProsohmDataGrid
        {...gridProps}
        loading={loading || gridProps.loading}
        pagination={false}
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
