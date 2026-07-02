import { useMemo, type ComponentProps } from 'react';
import { Box, useTheme } from '@mui/material';
import { DataGrid, type GridValidRowModel } from '@mui/x-data-grid';
import { prosohmDataGridSx } from '../../../theme/componentStyles';

type DataGridProps<R extends GridValidRowModel> = ComponentProps<typeof DataGrid<R>>;

interface ProsohmDataGridProps<R extends GridValidRowModel = GridValidRowModel>
  extends Omit<DataGridProps<R>, 'sx'> {
  sx?: DataGridProps<R>['sx'];
  onRowOpen?: (rowId: string) => void;
}

export function ProsohmDataGrid<R extends GridValidRowModel = GridValidRowModel>({
  sx,
  onRowOpen,
  onRowClick,
  ...props
}: ProsohmDataGridProps<R>) {
  const theme = useTheme();
  const gridSx = useMemo(() => prosohmDataGridSx(theme), [theme]);

  return (
    <Box sx={{ width: '100%' }}>
      <DataGrid
        disableRowSelectionOnClick
        {...props}
        onRowClick={(params, event, details) => {
          onRowOpen?.(String(params.id));
          onRowClick?.(params, event, details);
        }}
        sx={[gridSx, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])]}
      />
    </Box>
  );
}
