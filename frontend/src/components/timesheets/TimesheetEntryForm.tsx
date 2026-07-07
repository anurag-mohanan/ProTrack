import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import type { Project, TaskType, TimesheetEntry } from '../../types';
import { ProsohmButton } from '../ui/ProsohmButton';
import { TimesheetSelectionLine } from './TimesheetSelectionLine';
import { TimesheetToolNumberSelect } from './TimesheetToolNumberSelect';
import {
  buildToolOptions,
  LAST_TASK_KEY,
  LAST_TOOL_KEY,
  isLeaveToolOption,
  npTaskLabel,
  pushRecentTool,
  toolOptionFromEntry,
  type TimesheetToolOption,
} from './timesheetToolOptions';
import type { NonProductiveCode } from '../../types';
import { todayIsoDate } from '../../utils/timesheetMonth';

export interface TimesheetEntryFormValues {
  entryDate: string;
  toolValue: string;
  taskTypeId: string;
  hours: string;
  notes: string;
  isBillable: boolean;
}

interface TimesheetEntryFormProps {
  projects: Project[];
  npCodes: NonProductiveCode[];
  taskTypes: TaskType[];
  dailyTotals: Map<string, number>;
  dailyLimit: number;
  readOnly: boolean;
  canOverrideBillable: boolean;
  editingEntry: TimesheetEntry | null;
  saving: boolean;
  onSubmit: (values: TimesheetEntryFormValues) => Promise<void>;
  onCancelEdit: () => void;
  onEntryDateChange?: (entryDate: string) => void;
  variant?: 'inline' | 'dialog';
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
    isBillable: true,
  };
}

function defaultBillableForTool(
  tool: TimesheetToolOption | null,
  override?: boolean,
): boolean {
  if (tool?.kind === 'np') return override ?? false;
  if (tool?.kind === 'project') return override ?? true;
  return true;
}

export function TimesheetEntryForm({
  projects,
  npCodes,
  taskTypes,
  readOnly,
  canOverrideBillable,
  editingEntry,
  dailyTotals,
  dailyLimit,
  saving,
  onSubmit,
  onCancelEdit,
  onEntryDateChange,
  variant = 'inline',
}: TimesheetEntryFormProps) {
  const toolOptions = useMemo(() => buildToolOptions(projects, npCodes), [projects, npCodes]);
  const [form, setForm] = useState<TimesheetEntryFormValues>(emptyForm);
  const toolRef = useRef<HTMLInputElement>(null);
  const taskRef = useRef<HTMLInputElement>(null);
  const hoursRef = useRef<HTMLInputElement>(null);
  const notesRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingEntry) {
      const toolValue = toolOptionFromEntry(editingEntry);
      setForm({
        entryDate: editingEntry.entry_date,
        toolValue,
        taskTypeId: editingEntry.task_type_id ?? '',
        hours: String(editingEntry.hours),
        notes: editingEntry.description ?? '',
        isBillable: editingEntry.is_billable,
      });
      return;
    }
    setForm(emptyForm());
  }, [editingEntry, toolOptions]);

  useEffect(() => {
    onEntryDateChange?.(form.entryDate);
  }, [form.entryDate, onEntryDateChange]);

  const selectedTool =
    toolOptions.find((option) => option.value === form.toolValue) ?? null;
  const selectedProject =
    selectedTool?.kind === 'project'
      ? projects.find((project) => project.id === selectedTool.projectId) ?? null
      : null;

  const taskOptions = useMemo(() => {
    if (selectedTool?.kind !== 'project') return [];
    const active = taskTypes.filter((task) => task.is_active !== false);
    if (!selectedProject) return active;
    // Prefer the selected project's stream, but never hide the rest so the
    // Task dropdown is always populated when active task types exist.
    return [...active].sort((left, right) => {
      const leftMatch = left.stream_id === selectedProject.stream_id ? 0 : 1;
      const rightMatch = right.stream_id === selectedProject.stream_id ? 0 : 1;
      if (leftMatch !== rightMatch) return leftMatch - rightMatch;
      return left.name.localeCompare(right.name);
    });
  }, [selectedProject, selectedTool, taskTypes]);

  const projectedDailyTotal =
    (dailyTotals.get(form.entryDate) ?? 0) -
    (editingEntry && editingEntry.entry_date === form.entryDate
      ? Number(editingEntry.hours)
      : 0) +
    (Number(form.hours) || 0);
  const dailyWarning = projectedDailyTotal > dailyLimit;

  const resetAfterSave = (saved: TimesheetEntryFormValues) => {
    writeStored(LAST_TOOL_KEY, saved.toolValue);
    if (saved.taskTypeId) writeStored(LAST_TASK_KEY, saved.taskTypeId);
    pushRecentTool(saved.toolValue);
    setForm({
      entryDate: saved.entryDate,
      toolValue: saved.toolValue,
      taskTypeId: saved.taskTypeId,
      hours: '',
      notes: '',
      isBillable: defaultBillableForTool(
        toolOptions.find((option) => option.value === saved.toolValue) ?? null,
      ),
    });
    toolRef.current?.focus();
  };

  const handleSubmit = async (event?: FormEvent) => {
    event?.preventDefault();
    try {
      await onSubmit(form);
      if (!editingEntry) {
        resetAfterSave(form);
      }
    } catch {
      // Validation and save errors are surfaced by the page.
    }
  };

  const handleToolChange = (option: TimesheetToolOption | null) => {
    setForm((current) => ({
      ...current,
      toolValue: option?.value ?? '',
      taskTypeId: option?.kind === 'project' ? current.taskTypeId : '',
      isBillable: isLeaveToolOption(option)
        ? false
        : defaultBillableForTool(option),
    }));
  };

  const billableDisabled =
    readOnly ||
    saving ||
    isLeaveToolOption(selectedTool) ||
    (!canOverrideBillable && selectedTool?.kind === 'np');

  return (
    <Box
      component="form"
      onSubmit={(event) => void handleSubmit(event)}
      sx={
        variant === 'dialog'
          ? { pt: 0.5 }
          : {
              p: 1.5,
              borderRadius: 2,
              border: 1,
              borderColor: 'divider',
              bgcolor: 'background.paper',
              mb: 1.5,
            }
      }
    >
      {editingEntry && variant === 'inline' ? (
        <Typography variant="caption" color="primary.main" sx={{ display: 'block', mb: 1, fontWeight: 700 }}>
          Editing entry — save or cancel to return to quick entry
        </Typography>
      ) : null}

      {toolOptions.length === 0 ? (
        <Alert severity="info" sx={{ mb: 1, py: 0 }}>
          No tool numbers loaded ({projects.length} live projects, {npCodes.length} NP codes).
          Check that lookup data has loaded.
        </Alert>
      ) : null}

      <Stack
        direction="row"
        spacing={1}
        useFlexGap
        sx={{ width: '100%', flexWrap: 'wrap', alignItems: 'flex-start' }}
      >
        <TextField
          label="Date"
          type="date"
          size="small"
          required
          disabled={readOnly || saving}
          value={form.entryDate}
          onChange={(event) =>
            setForm((current) => ({ ...current, entryDate: event.target.value }))
          }
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ width: 150, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
        />

        <Box sx={{ flex: '1 1 220px', minWidth: 200, maxWidth: 360 }}>
          <TimesheetToolNumberSelect
            value={selectedTool}
            options={toolOptions}
            disabled={readOnly || saving}
            inputRef={toolRef}
            onChange={handleToolChange}
            onKeyDown={(event: KeyboardEvent) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                if (selectedTool?.kind === 'project') {
                  taskRef.current?.focus();
                } else {
                  hoursRef.current?.focus();
                }
              }
            }}
          />
        </Box>

        <TextField
          select
          size="small"
          label="Task"
          required={selectedTool?.kind === 'project'}
          disabled={
            readOnly ||
            saving ||
            !selectedTool ||
            selectedTool.kind === 'np'
          }
          value={selectedTool?.kind === 'np' ? 'np' : form.taskTypeId}
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
          sx={{ width: 150, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
        >
          {selectedTool?.kind === 'np' ? (
            <MenuItem value="np">{npTaskLabel(selectedTool)}</MenuItem>
          ) : (
            [
              <MenuItem key="" value="">
                Select
              </MenuItem>,
              ...taskOptions.map((task) => (
                <MenuItem key={task.id} value={task.id}>
                  {task.name}
                </MenuItem>
              )),
            ]
          )}
        </TextField>

        <FormControlLabel
          sx={{ mt: 0.5, mr: 0 }}
          control={
            <Checkbox
              size="small"
              checked={form.isBillable}
              disabled={billableDisabled}
              onChange={(event) =>
                setForm((current) => ({ ...current, isBillable: event.target.checked }))
              }
            />
          }
          label="Billable"
        />

        <TextField
          label="Hours"
          size="small"
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
              notesRef.current?.focus();
            }
          }}
          sx={{ width: 88, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
        />

        <TextField
          label="Notes"
          size="small"
          disabled={readOnly || saving}
          value={form.notes}
          placeholder="Optional notes…"
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
          sx={{ flex: '1 1 180px', minWidth: 160, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
        />

        <ProsohmButton
          type="submit"
          size="small"
          buttonVariant="primary"
          startIcon={editingEntry ? undefined : <AddIcon />}
          disabled={readOnly || saving}
          loading={saving}
          sx={{ mt: 0.25, whiteSpace: 'nowrap' }}
        >
          {editingEntry ? 'Save' : 'Add Entry'}
        </ProsohmButton>

        {editingEntry ? (
          <ProsohmButton
            size="small"
            buttonVariant="outlined"
            disabled={saving}
            onClick={onCancelEdit}
            sx={{ mt: 0.25 }}
          >
            Cancel
          </ProsohmButton>
        ) : null}
      </Stack>

      <TimesheetSelectionLine
        selection={selectedTool}
        project={selectedProject}
        isBillable={form.isBillable}
      />

      {dailyWarning ? (
        <Alert severity="warning" sx={{ mt: 1, py: 0 }}>
          Daily total would reach {projectedDailyTotal.toFixed(1)} hours (limit {dailyLimit}).
        </Alert>
      ) : null}
    </Box>
  );
}
