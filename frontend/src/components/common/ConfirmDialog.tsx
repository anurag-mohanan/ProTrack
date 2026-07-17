import {
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Typography,
  useTheme,
} from '@mui/material';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import { Box } from '@mui/material';
import { ProsohmButton } from '../ui/ProsohmButton';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  recordName?: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onClose: () => void;
  loading?: boolean;
  danger?: boolean;
  icon?: typeof WarningAmberOutlinedIcon;
}

export function ConfirmDialog({
  open,
  title,
  message,
  recordName,
  confirmLabel = 'Confirm',
  onConfirm,
  onClose,
  loading = false,
  danger = false,
  icon: IconComponent = WarningAmberOutlinedIcon,
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
        <Box
          sx={{
            width: 36,
            height: 36,
            borderRadius: 2,
            display: 'grid',
            placeItems: 'center',
            bgcolor: danger ? 'error.main' : 'primary.main',
            color: danger ? 'error.contrastText' : 'primary.contrastText',
          }}
        >
          <IconComponent fontSize="small" />
        </Box>
        {title}
      </DialogTitle>
      <DialogContent sx={{ pt: 0 }}>
        {recordName ? (
          <Box
            sx={{
              mb: 2,
              p: 1.5,
              borderRadius: 2,
              bgcolor: 'grey.50',
              border: 1,
              borderColor: 'divider',
            }}
          >
            <Typography variant="body1" sx={{ fontWeight: 700 }}>
              {recordName}
            </Typography>
          </Box>
        ) : null}
        <DialogContentText sx={{ color: 'text.secondary', whiteSpace: 'pre-line' }}>
          {message}
        </DialogContentText>
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
