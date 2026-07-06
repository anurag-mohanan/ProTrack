import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '@mui/material';
import type { NonProductiveCode, Project, TaskType, TimesheetEntry } from '../../types';
import {
  TimesheetEntryForm,
  type TimesheetEntryFormValues,
} from './TimesheetEntryForm';

interface TimesheetEntryEditDialogProps {
  open: boolean;
  entry: TimesheetEntry | null;
  projects: Project[];
  npCodes: NonProductiveCode[];
  taskTypes: TaskType[];
  canOverrideBillable: boolean;
  dailyTotals: Map<string, number>;
  dailyLimit: number;
  saving: boolean;
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
            onSubmit={onSave}
            onCancelEdit={onClose}
            variant="dialog"
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
