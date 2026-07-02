import { alpha, type Theme } from '@mui/material/styles';

export function prosohmDataGridSx(theme: Theme) {
  return {
    border: `1px solid ${theme.palette.prosohm.border}`,
    borderRadius: '16px',
    backgroundColor: theme.palette.prosohm.card,
    '& .MuiDataGrid-columnHeaders': {
      backgroundColor: theme.palette.background.default,
      borderBottom: `1px solid ${theme.palette.prosohm.border}`,
      minHeight: '52px !important',
      maxHeight: '52px !important',
      position: 'sticky',
      top: 0,
      zIndex: 1,
    },
    '& .MuiDataGrid-columnHeaderTitle': {
      fontWeight: 700,
      fontSize: '0.75rem',
      letterSpacing: '0.04em',
      textTransform: 'uppercase',
      color: theme.palette.text.secondary,
    },
    '& .MuiDataGrid-row': {
      cursor: 'pointer',
      minHeight: '52px !important',
      maxHeight: '52px !important',
      transition: 'background-color 0.2s ease',
    },
    '& .MuiDataGrid-row:nth-of-type(even)': {
      backgroundColor: alpha(theme.palette.background.default, 0.65),
    },
    '& .MuiDataGrid-row:hover': {
      backgroundColor: theme.palette.prosohm.hover,
    },
    '& .MuiDataGrid-row.Mui-selected': {
      backgroundColor: alpha(theme.palette.primary.main, 0.08),
    },
    '& .MuiDataGrid-cell': {
      borderColor: theme.palette.prosohm.border,
      py: 1,
      fontSize: '0.875rem',
    },
    '& .MuiDataGrid-footerContainer': {
      borderTop: `1px solid ${theme.palette.prosohm.border}`,
    },
    '& .MuiDataGrid-virtualScroller': {
      overflow: 'visible',
    },
    '& .MuiDataGrid-main': {
      overflow: 'visible',
    },
  };
}

export function prosohmTableContainerSx(theme: Theme) {
  return {
    border: `1px solid ${theme.palette.prosohm.border}`,
    borderRadius: '16px',
    overflow: 'hidden',
    boxShadow: theme.palette.prosohm.shadowCard,
    backgroundColor: theme.palette.prosohm.card,
    '& .MuiTableHead-root': {
      position: 'sticky',
      top: 0,
      zIndex: 1,
    },
    '& .MuiTableRow-root': {
      transition: 'background-color 0.2s ease',
    },
    '& .MuiTableRow-root:hover': {
      backgroundColor: theme.palette.prosohm.hover,
    },
  };
}

export const DATA_GRID_ACTIONS_COLUMN_WIDTH = 96;
