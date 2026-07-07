import { useState, type MouseEvent } from 'react';
import {
  Box,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Tooltip,
} from '@mui/material';
import EditRoundedIcon from '@mui/icons-material/EditRounded';
import MoreVertRoundedIcon from '@mui/icons-material/MoreVertRounded';
import ArchiveRoundedIcon from '@mui/icons-material/ArchiveRounded';
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded';
import FileDownloadRoundedIcon from '@mui/icons-material/FileDownloadRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded';

interface ProjectRowActionsProps {
  onView?: () => void;
  onEdit: () => void;
  onArchive?: () => void;
  onDuplicate?: () => void;
  onExport?: () => void;
  onDelete?: () => void;
  showDelete?: boolean;
}

function stopRowClick(event: MouseEvent) {
  event.stopPropagation();
}

export function ProjectRowActions({
  onView,
  onEdit,
  onArchive,
  onDuplicate,
  onExport,
  onDelete,
  showDelete = false,
}: ProjectRowActionsProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const menuOpen = Boolean(anchorEl);

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
      {onView ? (
        <Tooltip title="View">
          <IconButton
            size="small"
            aria-label="View project"
            onClick={(event) => {
              stopRowClick(event);
              onView();
            }}
          >
            <VisibilityRoundedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ) : null}
      <Tooltip title="Edit">
        <IconButton
          size="small"
          aria-label="Edit project"
          onClick={(event) => {
            stopRowClick(event);
            onEdit();
          }}
        >
          <EditRoundedIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="More actions">
        <IconButton
          size="small"
          aria-label="More project actions"
          onClick={(event) => {
            stopRowClick(event);
            setAnchorEl(event.currentTarget);
          }}
        >
          <MoreVertRoundedIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Menu
        anchorEl={anchorEl}
        open={menuOpen}
        onClose={() => setAnchorEl(null)}
        onClick={(event) => stopRowClick(event)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { sx: { minWidth: 180, borderRadius: 2 } } }}
      >
        {onDuplicate ? (
          <MenuItem
            onClick={() => {
              setAnchorEl(null);
              onDuplicate();
            }}
          >
            <ListItemIcon>
              <ContentCopyRoundedIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Duplicate</ListItemText>
          </MenuItem>
        ) : null}
        {onArchive ? (
          <MenuItem
            onClick={() => {
              setAnchorEl(null);
              onArchive();
            }}
          >
            <ListItemIcon>
              <ArchiveRoundedIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Archive</ListItemText>
          </MenuItem>
        ) : null}
        {onExport ? (
          <MenuItem
            onClick={() => {
              setAnchorEl(null);
              onExport();
            }}
          >
            <ListItemIcon>
              <FileDownloadRoundedIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Export</ListItemText>
          </MenuItem>
        ) : null}
        {showDelete && onDelete ? (
          <MenuItem
            onClick={() => {
              setAnchorEl(null);
              onDelete();
            }}
            sx={{ color: 'error.main' }}
          >
            <ListItemIcon sx={{ color: 'error.main' }}>
              <DeleteOutlineRoundedIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Delete</ListItemText>
          </MenuItem>
        ) : null}
      </Menu>
    </Box>
  );
}
