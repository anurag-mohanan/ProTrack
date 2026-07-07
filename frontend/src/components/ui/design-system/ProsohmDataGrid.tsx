import { useMemo, type ComponentProps } from 'react';
import { Box, useTheme } from '@mui/material';
import { DataGrid, type GridValidRowModel } from '@mui/x-data-grid';
import { pinnedDataGridColumnSx, prosohmDataGridSx } from '../../../theme/componentStyles';
import { PINNED_LEFT_CELL_CLASS } from '../../../theme/componentStyles';
import { usePreferences } from '../../../context/PreferencesContext';

type DataGridProps<R extends GridValidRowModel> = ComponentProps<typeof DataGrid<R>>;

interface ProsohmDataGridProps<R extends GridValidRowModel = GridValidRowModel>
  extends Omit<DataGridProps<R>, 'sx'> {
  sx?: DataGridProps<R>['sx'];
  onRowOpen?: (rowId: string) => void;
  /** Pin these column fields to the left (sticky while scrolling). */
  pinLeftFields?: string[];
  pageSizeStorageKey?: string;
  /** Tighter row and header heights for data-dense engineering views. */
  dense?: boolean;
}

export function ProsohmDataGrid<R extends GridValidRowModel = GridValidRowModel>({
  sx,
  onRowOpen,
  onRowClick,
  columns: columnsProp,
  pinLeftFields = [],
  pageSizeStorageKey = 'protrack:grid:page-size',
  dense = false,
  ...props
}: ProsohmDataGridProps<R>) {
  const theme = useTheme();
  const { preferences } = usePreferences();
  const gridSx = useMemo(() => prosohmDataGridSx(theme), [theme]);
  const pinnedSx = useMemo(() => pinnedDataGridColumnSx(theme), [theme]);
  const compactPreference = preferences?.table_density === 'compact';
  const rowHeight = dense ? 40 : compactPreference ? 44 : 52;
  const headerHeight = dense ? 38 : compactPreference ? 42 : 48;
  const persistedPageSize = Number(window.localStorage.getItem(pageSizeStorageKey) ?? 0);
  const defaultOption = props.pageSizeOptions?.[0];
  const fallbackPageSize =
    typeof defaultOption === 'number'
      ? defaultOption
      : defaultOption && 'value' in defaultOption
        ? Number(defaultOption.value)
        : 25;
  const resolvedPageSize =
    props.paginationModel?.pageSize ??
    (persistedPageSize > 0 ? persistedPageSize : fallbackPageSize);

  const columns = useMemo(() => {
    if (!pinLeftFields.length || !columnsProp) return columnsProp;
    const pinSet = new Set(pinLeftFields);
    return columnsProp.map((col) =>
      pinSet.has(col.field)
        ? {
            ...col,
            headerClassName: [col.headerClassName, PINNED_LEFT_CELL_CLASS].filter(Boolean).join(' '),
            cellClassName: [col.cellClassName, PINNED_LEFT_CELL_CLASS].filter(Boolean).join(' '),
          }
        : col,
    );
  }, [columnsProp, pinLeftFields]);

  return (
    <Box sx={{ width: '100%' }}>
      <DataGrid
        disableRowSelectionOnClick
        columnHeaderHeight={headerHeight}
        rowHeight={rowHeight}
        {...props}
        paginationModel={
          props.paginationModel ?? {
            page: 0,
            pageSize: resolvedPageSize,
          }
        }
        columns={columns}
        onPaginationModelChange={(model, details) => {
          if (model.pageSize) {
            window.localStorage.setItem(pageSizeStorageKey, String(model.pageSize));
          }
          props.onPaginationModelChange?.(model, details);
        }}
        onRowClick={(params, event, details) => {
          onRowOpen?.(String(params.id));
          onRowClick?.(params, event, details);
        }}
        sx={[
          gridSx,
          pinnedSx,
          dense
            ? {
                '& .MuiDataGrid-row': {
                  minHeight: '40px !important',
                  maxHeight: '40px !important',
                },
                '& .MuiDataGrid-columnHeaders': {
                  minHeight: '38px !important',
                  maxHeight: '38px !important',
                },
                '& .MuiDataGrid-cell': {
                  py: 0.5,
                  fontSize: '0.8rem',
                },
              }
            : undefined,
          ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
        ]}
      />
    </Box>
  );
}
