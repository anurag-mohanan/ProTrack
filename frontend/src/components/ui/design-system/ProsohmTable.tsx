import type { ReactNode } from 'react';
import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  useTheme,
} from '@mui/material';
import { prosohmTableContainerSx } from '../../../theme/componentStyles';

interface ProsohmTableProps {
  head: ReactNode;
  children: ReactNode;
  stickyHeader?: boolean;
  size?: 'small' | 'medium';
  onRowClick?: (index: number) => void;
  rowCount?: number;
}

export function ProsohmTable({
  head,
  children,
  stickyHeader = true,
  size = 'small',
}: ProsohmTableProps) {
  const theme = useTheme();

  return (
    <TableContainer component={Paper} sx={prosohmTableContainerSx(theme)}>
      <Table size={size} stickyHeader={stickyHeader}>
        <TableHead>{head}</TableHead>
        <TableBody>{children}</TableBody>
      </Table>
    </TableContainer>
  );
}

interface ClickableTableRowProps {
  children: ReactNode;
  onClick?: () => void;
  selected?: boolean;
}

export function ClickableTableRow({ children, onClick, selected }: ClickableTableRowProps) {
  return (
    <TableRow
      hover
      onClick={onClick}
      selected={selected}
      sx={{
        cursor: onClick ? 'pointer' : 'default',
        '&.Mui-selected': {
          bgcolor: 'action.selected',
        },
      }}
    >
      {children}
    </TableRow>
  );
}

export function EmptyTableCell({ colSpan, message = 'No records found.' }: { colSpan: number; message?: string }) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} align="center" sx={{ py: 4, color: 'text.secondary' }}>
        {message}
      </TableCell>
    </TableRow>
  );
}
