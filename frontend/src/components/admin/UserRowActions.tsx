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
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import LockResetRoundedIcon from '@mui/icons-material/LockResetRounded';
import VpnKeyOutlinedIcon from '@mui/icons-material/VpnKeyOutlined';
import LockOpenRoundedIcon from '@mui/icons-material/LockOpenRounded';
import type { User } from '../../types';

interface UserRowActionsProps {
  user: User;
  isAdmin: boolean;
  onEdit: () => void;
  onDelete?: () => void;
  onSetDefaultPassword: () => void;
  onResetRandomPassword: () => void;
  onUnlock?: () => void;
}

function stopRowClick(event: MouseEvent) {
  event.stopPropagation();
}

export function UserRowActions({
  user,
  isAdmin,
  onEdit,
  onDelete,
  onSetDefaultPassword,
  onResetRandomPassword,
  onUnlock,
}: UserRowActionsProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const menuOpen = Boolean(anchorEl);

  return (
    <Box sx={{ display: 'flex', gap: 0.25, alignItems: 'center' }}>
      <Tooltip title="Edit">
        <IconButton
          size="small"
          aria-label="Edit user"
          onClick={(event) => {
            stopRowClick(event);
            onEdit();
          }}
        >
          <EditIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Password actions">
        <IconButton
          size="small"
          aria-label="Password actions"
          onClick={(event) => {
            stopRowClick(event);
            setAnchorEl(event.currentTarget);
          }}
        >
          <VpnKeyOutlinedIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Menu
        anchorEl={anchorEl}
        open={menuOpen}
        onClose={() => setAnchorEl(null)}
        onClick={(event) => stopRowClick(event)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { sx: { minWidth: 220, borderRadius: 2 } } }}
      >
        <MenuItem
          onClick={() => {
            setAnchorEl(null);
            onSetDefaultPassword();
          }}
        >
          <ListItemIcon>
            <LockResetRoundedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText
            primary="Set default password"
            secondary="Prosohm@2026"
          />
        </MenuItem>
        <MenuItem
          onClick={() => {
            setAnchorEl(null);
            onResetRandomPassword();
          }}
        >
          <ListItemIcon>
            <VpnKeyOutlinedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText
            primary="Generate random password"
            secondary="Must change on next login"
          />
        </MenuItem>
        {user.is_locked && onUnlock ? (
          <MenuItem
            onClick={() => {
              setAnchorEl(null);
              onUnlock();
            }}
          >
            <ListItemIcon>
              <LockOpenRoundedIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText primary="Unlock account" />
          </MenuItem>
        ) : null}
      </Menu>
      {isAdmin && onDelete ? (
        <Tooltip title="Delete">
          <IconButton
            size="small"
            color="error"
            aria-label="Delete user"
            onClick={(event) => {
              stopRowClick(event);
              onDelete();
            }}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ) : null}
    </Box>
  );
}
