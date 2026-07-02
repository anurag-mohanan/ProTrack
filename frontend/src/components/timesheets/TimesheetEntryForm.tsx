import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Alert, Box, Grid, MenuItem, TextField, Typography } from '@mui/material';
import type { Project, TaskType, TimesheetEntry } from '../../types';
import { FormField } from '../ui/design-system';
import { ProsohmButton } from '../ui/ProsohmButton';
import { TimesheetProjectInfoPanel } from './TimesheetProjectInfoPanel';
import { TimesheetToolNumberSelect } from './TimesheetToolNumberSelect';
import {
  buildToolOptions,
  toolOptionFromEntry,
  type TimesheetToolOption,
} from './timesheetToolOptions';
import type { NonProductiveCode } from '../../types';
import { todayIsoDate } from '../../utils/timesheetMonth';

const LAST_TOOL_KEY = 'protrack.timesheet.lastTool';
const LAST_TASK_KEY = 'protrack.timesheet.lastTask';

export interface TimesheetEntryFormValues {
  entryDate: string;
  toolValue: string;
  taskTypeId: string;
  hours: string;
  notes: string;
}

interface TimesheetEntryFormProps {
  monthLabel: string;
  projects: Project[];
  npCodes: NonProductiveCode[];
  taskTypes: TaskType[];
  dailyTotals: Map<string, number>;
  dailyLimit: number;
  readOnly: boolean;
  editingEntry: TimesheetEntry | null;
  saving: boolean;
  onSubmit: (values: TimesheetEntryFormValues) => Promise<void>;
  onCancelEdit: () => void;
}

function readStored(key: string): string {
  try {
    return localStorage.getItem(key) ?? '';
  } catch {
    return '';
  }
}

function writeStored(key: string, value: string) {
  try {
    if (value) localStorage.setItem(key, value);
  } catch {
    // ignore storage failures
  }
}

function emptyForm(): TimesheetEntryFormValues {
  return {
    entryDate: todayIsoDate(),
    toolValue: readStored(LAST_TOOL_KEY),
    taskTypeId: readStored(LAST_TASK_KEY),
    hours: '',
    notes: '',
  };
}

export function TimesheetEntryForm({
  monthLabel,
  projects,
  npCodes,
  taskTypes,
  readOnly,
  editingEntry,
  dailyTotals,
  dailyLimit,
  saving,
  onSubmit,
  onCancelEdit,
}: TimesheetEntryFormProps) {
  const toolOptions = useMemo(() => buildToolOptions(projects, npCodes), [projects, npCodes]);
  const [form, setForm] = useState<TimesheetEntryFormValues>(emptyForm);
  const hoursRef = useRef<HTMLInputElement>(null);
  const notesRef = useRef<HTMLInputElement>(null);
  const taskRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingEntry) {
      setForm({
        entryDate: editingEntry.entry_date,
        toolValue: toolOptionFromEntry(editingEntry),
        taskTypeId: editingEntry.task_type_id ?? '',
        hours: String(editingEntry.hours),
        notes: editingEntry.description ?? '',
      });
      return;
    }
    setForm(emptyForm());
  }, [editingEntry]);

  const selectedTool =
    toolOptions.find((option) => option.value === form.toolValue) ?? null;
  const selectedProject =
    selectedTool?.kind === 'project'
      ? projects.find((project) => project.id === selectedTool.projectId) ?? null
      : null;

  const taskOptions = useMemo(() => {
    if (selectedTool?.kind !== 'project' || !selectedProject) return [];
    return taskTypes.filter((task) => task.stream_id === selectedProject.stream_id);
  }, [selectedProject, selectedTool, taskTypes]);

  const projectedDailyTotal =
    (dailyTotals.get(form.entryDate) ?? 0) -
    (editingEntry && editingEntry.entry_date === form.entryDate
      ? Number(editingEntry.hours)
      : 0) +
    (Number(form.hours) || 0);
  const dailyWarning = projectedDailyTotal > dailyLimit;

  const handleSubmit = async (event?: FormEvent) => {
    event?.preventDefault();
    await onSubmit(form);
    if (!editingEntry) {
      writeStored(LAST_TOOL_KEY, form.toolValue);
      if (form.taskTypeId) writeStored(LAST_TASK_KEY, form.taskTypeId);
      setForm({
        ...emptyForm(),
        toolValue: form.toolValue,
        taskTypeId: form.taskTypeId,
      });
      hoursRef.current?.focus();
    }
  };

  const handleToolKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      if (selectedTool?.kind === 'project') {
        taskRef.current?.focus();
      } else {
        hoursRef.current?.focus();
      }
    }
  };

  return (
    <Box
      component="form"
      onSubmit={(event) => void handleSubmit(event)}
      sx={{
        p: 2.5,
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        mb: 2,
      }}
    >
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
        {editingEntry ? 'Edit Timesheet Entry' : 'Add Timesheet Entry'}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {monthLabel} · Press Enter in Hours to save and start the next entry
      </Typography>

      {dailyWarning ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Daily total would reach {projectedDailyTotal.toFixed(1)} hours (limit {dailyLimit}).
        </Alert>
      ) : null}

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <FormField
                label="Date"
                type="date"
                required
                disabled={readOnly || saving}
                value={form.entryDate}
                onChange={(event) =>
                  setForm((current) => ({ ...current, entryDate: event.target.value }))
                }
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 5 }}>
              <TimesheetToolNumberSelect
                value={selectedTool}
                options={toolOptions}
                disabled={readOnly || saving}
                onChange={(option: TimesheetToolOption | null) =>
                  setForm((current) => ({
                    ...current,
                    toolValue: option?.value ?? '',
                    taskTypeId:
                      option?.kind === 'project' ? current.taskTypeId : '',
                  }))
                }
                onKeyDown={handleToolKeyDown}
              />
            </Grid>
            {selectedTool?.kind === 'project' ? (
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <TextField
                  select
                  fullWidth
                  required
                  label="Task"
                  disabled={readOnly || saving || !selectedProject}
                  value={form.taskTypeId}
                  inputRef={taskRef}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, taskTypeId: event.target.value }))
                  }
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      hoursRef.current?.focus();
                    }
                  }}
                  sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2.5 } }}
                >
                  <MenuItem value="">Select task</MenuItem>
                  {taskOptions.map((task) => (
                    <MenuItem key={task.id} value={task.id}>
                      {task.name}
                    </MenuItem>
                  ))}
                </TextField>
              </Grid>
            ) : null}
            <Grid size={{ xs: 12, sm: 4, md: 2 }}>
              <FormField
                label="Hours"
                required
                disabled={readOnly || saving}
                value={form.hours}
                inputRef={hoursRef}
                onChange={(event) =>
                  setForm((current) => ({ ...current, hours: event.target.value }))
                }
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    void handleSubmit();
                  }
                  if (event.key === 'Tab' && !event.shiftKey) {
                    event.preventDefault();
                    notesRef.current?.focus();
                  }
                }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 8, md: selectedTool?.kind === 'project' ? 12 : 6 }}>
              <FormField
                label="Notes"
                disabled={readOnly || saving}
                value={form.notes}
                inputRef={notesRef}
                onChange={(event) =>
                  setForm((current) => ({ ...current, notes: event.target.value }))
                }
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    void handleSubmit();
                  }
                }}
              />
            </Grid>
          </Grid>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <TimesheetProjectInfoPanel selection={selectedTool} project={selectedProject} />
        </Grid>
      </Grid>

      <Box sx={{ display: 'flex', gap: 1, mt: 2, flexWrap: 'wrap' }}>
        <ProsohmButton
          type="submit"
          buttonVariant="primary"
          disabled={readOnly || saving}
          loading={saving}
        >
          {editingEntry ? 'Save Changes' : 'Add Entry'}
        </ProsohmButton>
        {editingEntry ? (
          <ProsohmButton buttonVariant="outlined" disabled={saving} onClick={onCancelEdit}>
            Cancel Edit
          </ProsohmButton>
        ) : null}
      </Box>
    </Box>
  );
}
