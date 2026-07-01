import DeleteOutlineOutlinedIcon from '@mui/icons-material/DeleteOutlineOutlined';
import { ConfirmDialog } from '../../common/ConfirmDialog';

interface DeleteDialogProps {
  open: boolean;
  objectLabel: string;
  objectName: string;
  onConfirm: () => void;
  onClose: () => void;
  loading?: boolean;
  extraMessage?: string;
}

export function DeleteDialog({
  open,
  objectLabel,
  objectName,
  onConfirm,
  onClose,
  loading = false,
  extraMessage,
}: DeleteDialogProps) {
  return (
    <ConfirmDialog
      open={open}
      title={`Delete ${objectLabel}`}
      message={
        extraMessage
          ? `Are you sure you want to delete "${objectName}"? ${extraMessage}`
          : `Are you sure you want to delete "${objectName}"? This action cannot be undone.`
      }
      confirmLabel={`Delete ${objectLabel}`}
      onConfirm={onConfirm}
      onClose={onClose}
      loading={loading}
      danger
      icon={DeleteOutlineOutlinedIcon}
    />
  );
}
