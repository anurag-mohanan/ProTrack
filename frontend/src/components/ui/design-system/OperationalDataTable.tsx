import type { ReactNode } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  type TableCellProps,
  TableContainer,
  TableHead,
  useTheme,
} from '@mui/material';
import {
  PINNED_LEFT_CELL_CLASS,
  prosohmTableContainerSx,
  zebraRowSx,
} from '../../../theme/componentStyles';

interface OperationalDataTableProps {
  head: ReactNode;
  children: ReactNode;
  maxHeight?: number | string;
  stickyFirstColumn?: boolean;
  size?: 'small' | 'medium';
}

export function OperationalDataTable({
  head,
  children,
  maxHeight = 560,
  stickyFirstColumn = false,
  size = 'small',
}: OperationalDataTableProps) {
  const theme = useTheme();

  return (
    <TableContainer
      sx={{
        ...prosohmTableContainerSx(theme),
        maxHeight,
        overflow: 'auto',
      }}
    >
      <Table size={size} stickyHeader>
        <TableHead>
          {stickyFirstColumn
            ? head
            : head}
        </TableHead>
        <TableBody sx={zebraRowSx}>{children}</TableBody>
      </Table>
    </TableContainer>
  );
}

export function StickyTableCell({
  children,
  align,
  pinned = false,
  sx,
}: {
  children: ReactNode;
  align?: 'left' | 'right' | 'center';
  pinned?: boolean;
  sx?: TableCellProps['sx'];
}) {
  return (
    <TableCell
      align={align}
      className={pinned ? PINNED_LEFT_CELL_CLASS : undefined}
      sx={{
        ...(pinned
          ? {
              position: 'sticky',
              left: 0,
              zIndex: 2,
              bgcolor: 'background.paper',
              boxShadow: '2px 0 6px rgba(15,23,42,0.06)',
              fontWeight: 700,
            }
          : null),
        ...sx,
      }}
    >
      {children}
    </TableCell>
  );
}

export function StickyHeaderCell({
  children,
  align,
  pinned = false,
}: {
  children: ReactNode;
  align?: 'left' | 'right' | 'center';
  pinned?: boolean;
}) {
  return (
    <TableCell
      align={align}
      className={pinned ? PINNED_LEFT_CELL_CLASS : undefined}
      sx={
        pinned
          ? {
              position: 'sticky',
              left: 0,
              zIndex: 3,
              bgcolor: 'background.default',
              boxShadow: '2px 0 6px rgba(15,23,42,0.06)',
            }
          : undefined
      }
    >
      {children}
    </TableCell>
  );
}
