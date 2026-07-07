import { alpha, type Theme } from '@mui/material/styles';
import { designTokens } from './designTokens';

export function prosohmDataGridSx(theme: Theme) {
  return {
    border: `1px solid ${theme.palette.divider}`,
    borderRadius: `${designTokens.radius.lg}px`,
    backgroundColor: designTokens.semantic.card,
    boxShadow: designTokens.elevation.card,
    overflow: 'hidden',
    '& .MuiDataGrid-columnHeaders': {
      backgroundColor: designTokens.semantic.neutralSoft,
      borderBottom: `1px solid ${theme.palette.divider}`,
      minHeight: '48px !important',
      maxHeight: '48px !important',
      position: 'sticky',
      top: 0,
      zIndex: 2,
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
    border: `1px solid ${theme.palette.divider}`,
    borderRadius: `${designTokens.radius.lg}px`,
    overflow: 'hidden',
    boxShadow: designTokens.elevation.card,
    backgroundColor: designTokens.semantic.card,
    '& .MuiTableHead-root': {
      position: 'sticky',
      top: 0,
      zIndex: 2,
      bgcolor: designTokens.semantic.neutralSoft,
    },
    '& .MuiTableCell-head': {
      fontWeight: 700,
      fontSize: '0.75rem',
      letterSpacing: '0.04em',
      textTransform: 'uppercase',
      color: theme.palette.text.secondary,
      py: 1.25,
    },
    '& .MuiTableCell-body': {
      py: 1.25,
      fontSize: '0.875rem',
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
