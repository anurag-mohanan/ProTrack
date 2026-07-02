import type { MouseEvent, ReactNode } from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import ArchiveIcon from '@mui/icons-material/Archive';

interface TableRowActionsProps {
  onEdit: () => void;
  onArchive?: () => void;
  archiveLabel?: string;
  deleteAction?: ReactNode;
  editLabel?: string;
}

function stopRowClick(event: MouseEvent) {
  event.stopPropagation();
}

export function TableRowActions({
  onEdit,
  onArchive,
  archiveLabel = 'Archive',
  deleteAction,
  editLabel = 'Edit',
}: TableRowActionsProps) {
  return (
    <Box sx={{ display: 'flex', gap: 0.25, alignItems: 'center' }}>
      <Tooltip title={editLabel}>
        <IconButton
          size="small"
          aria-label={editLabel}
          onClick={(event) => {
            stopRowClick(event);
            onEdit();
          }}
        >
          <EditIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      {onArchive ? (
        <Tooltip title={archiveLabel}>
          <IconButton
            size="small"
            aria-label={archiveLabel}
            onClick={(event) => {
              stopRowClick(event);
              onArchive();
            }}
          >
            <ArchiveIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ) : null}
      {deleteAction ? (
        <Box
          onClick={stopRowClick}
          sx={{ display: 'inline-flex', alignItems: 'center' }}
        >
          {deleteAction}
        </Box>
      ) : null}
    </Box>
  );
}
