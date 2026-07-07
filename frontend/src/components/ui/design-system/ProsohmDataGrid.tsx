import { useMemo, type ComponentProps } from 'react';
import { Box, useTheme } from '@mui/material';
import { DataGrid, type GridValidRowModel } from '@mui/x-data-grid';
import { pinnedDataGridColumnSx, prosohmDataGridSx } from '../../../theme/componentStyles';
import { PINNED_LEFT_CELL_CLASS } from '../../../theme/componentStyles';

type DataGridProps<R extends GridValidRowModel> = ComponentProps<typeof DataGrid<R>>;

interface ProsohmDataGridProps<R extends GridValidRowModel = GridValidRowModel>
  extends Omit<DataGridProps<R>, 'sx'> {
  sx?: DataGridProps<R>['sx'];
  onRowOpen?: (rowId: string) => void;
  /** Pin these column fields to the left (sticky while scrolling). */
  pinLeftFields?: string[];
}

export function ProsohmDataGrid<R extends GridValidRowModel = GridValidRowModel>({
  sx,
  onRowOpen,
  onRowClick,
  columns: columnsProp,
  pinLeftFields = [],
  ...props
}: ProsohmDataGridProps<R>) {
  const theme = useTheme();
  const gridSx = useMemo(() => prosohmDataGridSx(theme), [theme]);
  const pinnedSx = useMemo(() => pinnedDataGridColumnSx(theme), [theme]);

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
        columnHeaderHeight={48}
        rowHeight={52}
        {...props}
        columns={columns}
        onRowClick={(params, event, details) => {
          onRowOpen?.(String(params.id));
          onRowClick?.(params, event, details);
        }}
        sx={[gridSx, pinnedSx, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])]}
      />
    </Box>
  );
}
