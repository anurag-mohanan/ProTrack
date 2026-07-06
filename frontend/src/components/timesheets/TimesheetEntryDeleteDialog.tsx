import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import type { TimesheetEntry } from '../../types';
import { formatDate, formatNumber } from '../../utils/format';

interface TimesheetEntryDeleteDialogProps {
  entry: TimesheetEntry | null;
  open: boolean;
  loading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

function entryToolLabel(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    return entry.non_productive_code ?? 'NP';
  }
  return entry.project_tool_number ?? '—';
}

function entryTaskLabel(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    return entry.non_productive_description ?? 'Non-Productive';
  }
  return entry.task_type_name ?? '—';
}

export function TimesheetEntryDeleteDialog({
  entry,
  open,
  loading = false,
  onCancel,
  onConfirm,
}: TimesheetEntryDeleteDialogProps) {
  if (!entry) return null;

  return (
    <Dialog open={open} onClose={loading ? undefined : onCancel} maxWidth="xs" fullWidth>
      <DialogTitle>Delete this timesheet entry?</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>
          This action cannot be undone.
        </DialogContentText>
        <Stack spacing={0.5}>
          <Typography variant="body2">
            <strong>Date:</strong> {formatDate(entry.entry_date)}
          </Typography>
          <Typography variant="body2">
            <strong>Tool:</strong> {entryToolLabel(entry)}
          </Typography>
          <Typography variant="body2">
            <strong>Task:</strong> {entryTaskLabel(entry)}
          </Typography>
          <Typography variant="body2">
            <strong>Hours:</strong> {formatNumber(entry.hours, 1)}
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={loading}>
          Cancel
        </Button>
        <Button color="error" variant="contained" onClick={onConfirm} disabled={loading}>
          Delete
        </Button>
      </DialogActions>
    </Dialog>
  );
}
