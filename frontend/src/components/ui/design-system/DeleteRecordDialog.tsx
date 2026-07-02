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
import { formatDisplayValue } from '../../../utils/format';

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

function hasProjectBlockers(related: string[]): boolean {
  return related.some((item) => /project/i.test(item));
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
  const recordName = formatDisplayValue(check?.record_name, 'this record');
  const recordType = check?.record_type ?? 'Record';
  const blocked = Boolean(check && !check.can_delete);
  const related = check?.related_records ?? check?.blockers ?? [];
  const customerProjectBlock =
    blocked && recordType === 'Customer' && hasProjectBlockers(related);

  return (
    <ModernDrawer
      open={open}
      onClose={onClose}
      title={blocked ? `Delete ${recordType}` : `Delete ${recordType}`}
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
              Archive {recordType}
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
              Delete
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
                  {customerProjectBlock
                    ? 'This customer has active projects and cannot be deleted.'
                    : 'This record is currently in use and cannot be deleted.'}
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
                  {customerProjectBlock
                    ? 'Reassign or complete active projects before deleting this customer, or archive the customer instead.'
                    : 'Remove or reassign dependencies before permanent deletion. You can deactivate or archive this record instead.'}
                </Typography>
              </>
            ) : (
              <Alert severity="error" icon={<WarningAmberOutlinedIcon fontSize="inherit" />}>
                You are about to permanently delete{' '}
                <strong>{recordName}</strong>. This action cannot be undone.
              </Alert>
            )}
          </>
        )}
      </Box>
    </ModernDrawer>
  );
}
