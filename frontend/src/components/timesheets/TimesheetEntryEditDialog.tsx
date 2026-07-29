import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '@mui/material';
import type { NonProductiveCode, TaskType, TimesheetEntry } from '../../types';
import type { TimesheetProjectLookup } from '../../types/TimesheetEntry';
import {
  TimesheetEntryForm,
  type TimesheetEntryFormValues,
} from './TimesheetEntryForm';

interface TimesheetEntryEditDialogProps {
  open: boolean;
  entry: TimesheetEntry | null;
  projects: TimesheetProjectLookup[];
  npCodes: NonProductiveCode[];
  taskTypes: TaskType[];
  canOverrideBillable: boolean;
  dailyTotals: Map<string, number>;
  dailyLimit: number;
  saving: boolean;
  currentUserId?: string;
  onSave: (values: TimesheetEntryFormValues) => Promise<void>;
  onClose: () => void;
}

export function TimesheetEntryEditDialog({
  open,
  entry,
  projects,
  npCodes,
  taskTypes,
  canOverrideBillable,
  dailyTotals,
  dailyLimit,
  saving,
  currentUserId,
  onSave,
  onClose,
}: TimesheetEntryEditDialogProps) {
  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="lg" fullWidth>
      <DialogTitle>Edit Timesheet Entry</DialogTitle>
      <DialogContent>
        {entry ? (
          <TimesheetEntryForm
            projects={projects}
            npCodes={npCodes}
            taskTypes={taskTypes}
            readOnly={false}
            canOverrideBillable={canOverrideBillable}
            editingEntry={entry}
            dailyTotals={dailyTotals}
            dailyLimit={dailyLimit}
            saving={saving}
            currentUserId={currentUserId}
            onSubmit={onSave}
            onCancelEdit={onClose}
            variant="dialog"
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
