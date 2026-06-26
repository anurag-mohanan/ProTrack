import { alpha, type Theme } from '@mui/material/styles';

export function prosohmDataGridSx(theme: Theme) {
  return {
    border: `1px solid ${theme.palette.prosohm.border}`,
    borderRadius: '16px',
    backgroundColor: theme.palette.prosohm.card,
    '& .MuiDataGrid-columnHeaders': {
      backgroundColor: theme.palette.background.default,
      borderBottom: `1px solid ${theme.palette.prosohm.border}`,
      minHeight: '48px !important',
    },
    '& .MuiDataGrid-columnHeaderTitle': {
      fontWeight: 700,
      fontSize: '0.75rem',
      letterSpacing: '0.04em',
      textTransform: 'uppercase',
      color: theme.palette.text.secondary,
    },
    '& .MuiDataGrid-row:nth-of-type(even)': {
      backgroundColor: alpha(theme.palette.background.default, 0.65),
    },
    '& .MuiDataGrid-row:hover': {
      backgroundColor: theme.palette.prosohm.hover,
    },
    '& .MuiDataGrid-cell': {
      borderColor: theme.palette.prosohm.border,
    },
    '& .MuiDataGrid-footerContainer': {
      borderTop: `1px solid ${theme.palette.prosohm.border}`,
    },
    '& .MuiDataGrid-row': { cursor: 'pointer' },
    '& .MuiDataGrid-virtualScroller': {
      overflow: 'visible',
    },
    '& .MuiDataGrid-main': {
      overflow: 'visible',
    },
  };
}
