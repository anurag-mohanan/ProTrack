import {
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  useTheme,
} from '@mui/material';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import { Box } from '@mui/material';
import { ProsohmButton } from '../ui/ProsohmButton';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onClose: () => void;
  loading?: boolean;
  danger?: boolean;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  onConfirm,
  onClose,
  loading = false,
  danger = false,
}: ConfirmDialogProps) {
  const theme = useTheme();

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      slotProps={{
        paper: {
          sx: {
            borderRadius: 3,
            boxShadow: theme.palette.prosohm.shadowDialog,
            overflow: 'hidden',
          },
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5, pb: 1 }}>
        {danger ? (
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 2,
              display: 'grid',
              placeItems: 'center',
              bgcolor: 'error.main',
              color: 'error.contrastText',
            }}
          >
            <WarningAmberOutlinedIcon fontSize="small" />
          </Box>
        ) : null}
        {title}
      </DialogTitle>
      <DialogContent sx={{ pt: 0 }}>
        <DialogContentText sx={{ color: 'text.secondary' }}>{message}</DialogContentText>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <ProsohmButton buttonVariant="outlined" onClick={onClose} disabled={loading}>
          Cancel
        </ProsohmButton>
        <ProsohmButton
          buttonVariant={danger ? 'danger' : 'primary'}
          onClick={onConfirm}
          loading={loading}
        >
          {confirmLabel}
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}
