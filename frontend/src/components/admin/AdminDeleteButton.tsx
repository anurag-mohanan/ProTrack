import { IconButton, Tooltip } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { DeleteRecordDialog } from '../ui/design-system/DeleteRecordDialog';
import { ProsohmButton } from '../ui/ProsohmButton';
import { useAuth } from '../../context/AuthContext';
import { useAdminPermanentDelete } from '../../hooks/useAdminPermanentDelete';
import { canDeleteRecords } from '../../utils/permissions';

interface AdminDeleteButtonProps {
  resource: string;
  recordId: string;
  recordName: string;
  onDeleted: () => void;
  onDeactivate?: () => void | Promise<void>;
  onArchive?: () => void | Promise<void>;
  showArchive?: boolean;
  showDeactivate?: boolean;
  mode?: 'icon' | 'button';
  onClick?: (event: React.MouseEvent) => void;
}

export function AdminDeleteButton({
  resource,
  recordId,
  recordName,
  onDeleted,
  onDeactivate,
  onArchive,
  showArchive = false,
  showDeactivate = true,
  mode = 'icon',
  onClick,
}: AdminDeleteButtonProps) {
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { check, loading, isOpen, openDelete, closeDelete, confirmDelete } = useAdminPermanentDelete(
    resource,
    onDeleted,
  );

  if (!isAdmin) return null;

  const handleOpen = (event: React.MouseEvent) => {
    onClick?.(event);
    void openDelete(recordId, recordName);
  };

  return (
    <>
      {mode === 'button' ? (
        <ProsohmButton buttonVariant="danger" size="small" onClick={handleOpen}>
          Delete
        </ProsohmButton>
      ) : (
        <Tooltip title="Delete permanently">
          <IconButton size="small" color="error" onClick={handleOpen}>
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
      <DeleteRecordDialog
        open={isOpen}
        check={check}
        loading={loading}
        onClose={closeDelete}
        onConfirm={() => void confirmDelete()}
        onDeactivate={
          onDeactivate
            ? () => {
                void onDeactivate();
                closeDelete();
              }
            : undefined
        }
        onArchive={
          onArchive
            ? () => {
                void onArchive();
                closeDelete();
              }
            : undefined
        }
        showArchive={showArchive}
        showDeactivate={showDeactivate}
      />
    </>
  );
}
