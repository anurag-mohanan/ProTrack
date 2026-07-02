import DeleteForeverOutlinedIcon from '@mui/icons-material/DeleteForeverOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import {
  Alert,
  Box,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  Typography,
} from '@mui/material';
import { ModernDrawer } from './ModernDrawer';
import { ProsohmButton } from '../ProsohmButton';

export interface DeleteCheckResult {
  can_delete: boolean;
  blockers: string[];
  record_name: string | null;
  record_type: string | null;
  related_records: string[];
}

interface DeleteRecordDialogProps {
  open: boolean;
  check: DeleteCheckResult | null;
  loading?: boolean;
  onClose: () => void;
  onConfirm: () => void;
  onDeactivate?: () => void;
  onArchive?: () => void;
  showDeactivate?: boolean;
  showArchive?: boolean;
}

export function DeleteRecordDialog({
  open,
  check,
  loading = false,
  onClose,
  onConfirm,
  onDeactivate,
  onArchive,
  showDeactivate = true,
  showArchive = false,
}: DeleteRecordDialogProps) {
  const recordName = check?.record_name ?? 'this record';
  const recordType = check?.record_type ?? 'Record';
  const blocked = Boolean(check && !check.can_delete);
  const related = check?.related_records ?? check?.blockers ?? [];

  return (
    <ModernDrawer
      open={open}
      onClose={onClose}
      title={blocked ? 'Record In Use' : 'Permanent Delete'}
      subtitle={blocked ? 'Deletion is blocked by related data' : 'This action cannot be undone'}
      icon={blocked ? WarningAmberOutlinedIcon : DeleteForeverOutlinedIcon}
      width={520}
      footer={
        <>
          <ProsohmButton buttonVariant="outlined" onClick={onClose} disabled={loading}>
            Cancel
          </ProsohmButton>
          {blocked && showArchive && onArchive ? (
            <ProsohmButton buttonVariant="secondary" onClick={onArchive} disabled={loading}>
              Archive
            </ProsohmButton>
          ) : null}
          {blocked && showDeactivate && onDeactivate ? (
            <ProsohmButton buttonVariant="secondary" onClick={onDeactivate} disabled={loading}>
              Deactivate
            </ProsohmButton>
          ) : null}
          {!blocked ? (
            <ProsohmButton
              buttonVariant="danger"
              loading={loading}
              onClick={onConfirm}
              startIcon={<DeleteForeverOutlinedIcon />}
            >
              Delete Permanently
            </ProsohmButton>
          ) : null}
        </>
      }
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
        {!check ? (
          <Typography variant="body2" color="text.secondary">
            Checking dependencies…
          </Typography>
        ) : (
          <>
        <Box>
          <Typography variant="captionLabel" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
            Record Type
          </Typography>
          <Chip label={recordType} size="small" color="default" />
        </Box>

        <Box>
          <Typography variant="captionLabel" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
            Record Name
          </Typography>
          <Typography variant="body1" sx={{ fontWeight: 700 }}>
            {recordName}
          </Typography>
        </Box>

        <Divider />

        {blocked ? (
          <>
            <Alert severity="warning" icon={<WarningAmberOutlinedIcon fontSize="inherit" />}>
              This record is currently in use.
            </Alert>
            {related.length ? (
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Related Records
                </Typography>
                <List dense disablePadding>
                  {related.map((item) => (
                    <ListItem key={item} disableGutters sx={{ py: 0.25 }}>
                      <ListItemText primary={item} slotProps={{ primary: { variant: 'body2' } }} />
                    </ListItem>
                  ))}
                </List>
              </Box>
            ) : null}
            <Typography variant="body2" color="text.secondary">
              Remove or reassign dependencies before permanent deletion. You can deactivate or archive
              this record instead.
            </Typography>
          </>
        ) : (
          <Alert severity="error">
            You are about to permanently delete {recordType} &apos;{recordName}&apos;. This action
            cannot be undone.
          </Alert>
        )}
          </>
        )}
      </Box>
    </ModernDrawer>
  );
}
