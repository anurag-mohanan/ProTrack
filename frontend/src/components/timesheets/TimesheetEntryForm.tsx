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
import type { TaskType, TimesheetEntry } from '../../types';
import type { ContributionReason, PostCompletionWorkType, TimesheetProjectLookup } from '../../types/TimesheetEntry';
import {
  CONTRIBUTION_REASON_LABELS,
  isReworkQualityReason,
  POST_COMPLETION_COMMENT_TYPES,
  POST_COMPLETION_WORK_LABELS,
  REWORK_QUALITY_REASON,
} from '../../types/TimesheetEntry';
import { ProsohmButton } from '../ui/ProsohmButton';
import { TimesheetProjectContextPanel } from './TimesheetProjectContextPanel';
import { TimesheetToolNumberSelect } from './TimesheetToolNumberSelect';
import {
  buildToolOptions,
  LAST_BILLABLE_KEY,
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
import {
  resolveTaskTypeIdForProject,
  taskTypesForProjectStream,
} from '../../utils/timesheetTaskTypes';

export interface TimesheetEntryFormValues {
  entryDate: string;
  toolValue: string;
  taskTypeId: string;
  hours: string;
  notes: string;
  isBillable: boolean;
  contributionReason: string;
  postCompletionType: string;
}

interface TimesheetEntryFormProps {
  projects: TimesheetProjectLookup[];
  npCodes: NonProductiveCode[];
  taskTypes: TaskType[];
  dailyTotals: Map<string, number>;
  dailyLimit: number;
  readOnly: boolean;
  canOverrideBillable: boolean;
  editingEntry: TimesheetEntry | null;
  saving: boolean;
  currentUserId?: string;
  currentUserTeamId?: string | null;
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
  const storedBillable = readStored(LAST_BILLABLE_KEY);
  return {
    entryDate: todayIsoDate(),
    toolValue: readStored(LAST_TOOL_KEY),
    taskTypeId: readStored(LAST_TASK_KEY),
    hours: '',
    notes: '',
    isBillable: storedBillable ? storedBillable === 'true' : true,
    contributionReason: '',
    postCompletionType: '',
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
  currentUserId: _currentUserId,
  currentUserTeamId,
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
        contributionReason: editingEntry.contribution_reason ?? '',
        postCompletionType: editingEntry.post_completion_type ?? '',
      });
      return;
    }
    setForm(emptyForm());
    // Only re-sync when entering/leaving edit mode — not when tool options refresh
    // (search/refetch). Depending on toolOptions was resetting the form on every keystroke.
  }, [editingEntry]);

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
    return taskTypesForProjectStream(taskTypes, selectedProject?.stream_id).sort((left, right) =>
      left.name.localeCompare(right.name),
    );
  }, [selectedProject?.stream_id, selectedTool, taskTypes]);

  useEffect(() => {
    if (selectedTool?.kind !== 'project') return;
    const resolved = resolveTaskTypeIdForProject(
      taskTypes,
      selectedProject?.stream_id,
      form.taskTypeId,
    );
    if (resolved !== form.taskTypeId) {
      setForm((current) => ({ ...current, taskTypeId: resolved }));
    }
  }, [selectedProject?.stream_id, selectedTool?.kind, selectedTool?.value, taskTypes]);

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
      contributionReason: saved.contributionReason,
      postCompletionType:
        projects.find((project) => `project:${project.id}` === saved.toolValue)
          ?.execution_status === 'completed'
          ? saved.postCompletionType || 'additional_work'
          : '',
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
    const project =
      option?.kind === 'project'
        ? projects.find((item) => item.id === option.projectId) ?? null
        : null;
    setForm((current) => {
      const keepRework =
        option?.kind === 'project' && isReworkQualityReason(current.contributionReason);
      return {
        ...current,
        toolValue: option?.value ?? '',
        taskTypeId:
          option?.kind === 'project'
            ? resolveTaskTypeIdForProject(taskTypes, project?.stream_id, current.taskTypeId)
            : '',
        contributionReason: option?.kind === 'project' ? current.contributionReason : '',
        postCompletionType:
          project?.execution_status === 'completed' ? 'additional_work' : '',
        isBillable: isLeaveToolOption(option)
          ? false
          : keepRework
            ? false
            : defaultBillableForTool(option),
      };
    });
  };

  const handleContributionReasonChange = (value: string) => {
    setForm((current) => {
      if (isReworkQualityReason(value)) {
        writeStored(LAST_BILLABLE_KEY, 'false');
        return { ...current, contributionReason: value, isBillable: false };
      }
      if (isReworkQualityReason(current.contributionReason)) {
        writeStored(LAST_BILLABLE_KEY, 'true');
        return { ...current, contributionReason: value, isBillable: true };
      }
      return { ...current, contributionReason: value };
    });
  };

  const handleBillableChange = (next: boolean) => {
    writeStored(LAST_BILLABLE_KEY, String(next));
    setForm((current) => {
      if (!next && selectedTool?.kind === 'project') {
        // Unchecking Billable on project work marks it as rework for efficiency tracking.
        return {
          ...current,
          isBillable: false,
          contributionReason: REWORK_QUALITY_REASON,
        };
      }
      if (next && isReworkQualityReason(current.contributionReason)) {
        return { ...current, isBillable: true, contributionReason: '' };
      }
      return { ...current, isBillable: next };
    });
  };

  const isReworkEntry =
    selectedTool?.kind === 'project' && isReworkQualityReason(form.contributionReason);

  const billableDisabled =
    readOnly ||
    saving ||
    isLeaveToolOption(selectedTool) ||
    isReworkEntry ||
    (!canOverrideBillable && selectedTool?.kind === 'np');

  // Owners and contributors both need rework tagging for design-efficiency analysis.
  const showContributionReason = selectedTool?.kind === 'project' && Boolean(selectedProject);
  const isCompletedProject = selectedProject?.execution_status === 'completed';
  const postCompletionBlocked =
    isCompletedProject && selectedProject?.post_completion_hours_allowed === false;
  const commentRequiredForPostCompletion = POST_COMPLETION_COMMENT_TYPES.includes(
    form.postCompletionType as PostCompletionWorkType,
  );
  const isCrossTeamSupport = Boolean(
    selectedProject?.team_id &&
      currentUserTeamId &&
      selectedProject.team_id !== currentUserTeamId,
  );

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

      {isCompletedProject ? (
        <Alert severity="warning" sx={{ mb: 1.25 }}>
          Project Completed
          {postCompletionBlocked
            ? ' — this team or workstream does not allow post-completion timesheet hours.'
            : ' — hours logged now are post-completion work, not original project hours. Status stays Completed.'}
        </Alert>
      ) : null}

      {toolOptions.length === 0 ? (
        <Alert severity="info" sx={{ mb: 1, py: 0 }}>
          No tool numbers loaded ({projects.length} live projects, {npCodes.length} NP codes).
          Check that lookup data has loaded.
        </Alert>
      ) : null}

      {selectedTool?.kind === 'project' && selectedProject && taskOptions.length === 0 ? (
        <Alert severity="warning" sx={{ mb: 1, py: 0 }}>
          No task types are configured for this project&apos;s stream. Ask an administrator to add
          task types for the stream.
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
          slotProps={{ inputLabel: { shrink: true } }}
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

        {showContributionReason ? (
          <TextField
            select
            size="small"
            label="Contribution reason"
            disabled={readOnly || saving}
            value={form.contributionReason}
            onChange={(event) => handleContributionReasonChange(event.target.value)}
            helperText={
              isReworkEntry ? 'Logged as unbilled rework for design efficiency' : undefined
            }
            slotProps={{
              inputLabel: { shrink: true },
              formHelperText: { sx: { mx: 0, mt: 0.25, fontSize: '0.65rem' } },
            }}
            sx={{ width: 220, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
          >
            <MenuItem value="">None (billable)</MenuItem>
            {(Object.entries(CONTRIBUTION_REASON_LABELS) as [ContributionReason, string][]).map(
              ([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ),
            )}
          </TextField>
        ) : null}

        {isCompletedProject ? (
          <TextField
            select
            size="small"
            required
            label="Work Type"
            disabled={readOnly || saving || postCompletionBlocked}
            value={form.postCompletionType || 'additional_work'}
            onChange={(event) =>
              setForm((current) => ({ ...current, postCompletionType: event.target.value }))
            }
            helperText="Project is completed. Additional Work is the default — change it if this is rework or a customer/internal correction."
            slotProps={{
              inputLabel: { shrink: true },
              formHelperText: { sx: { mx: 0, mt: 0.25, fontSize: '0.65rem' } },
            }}
            sx={{ width: 220, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
          >
            <MenuItem value="" disabled>
              Normal Project Work
            </MenuItem>
            {(
              Object.entries(POST_COMPLETION_WORK_LABELS) as [PostCompletionWorkType, string][]
            ).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
        ) : null}

        <FormControlLabel
          sx={{ mt: 0.5, mr: 0 }}
          control={
            <Checkbox
              size="small"
              checked={form.isBillable}
              disabled={billableDisabled}
              onChange={(event) => handleBillableChange(event.target.checked)}
            />
          }
          label={isReworkEntry ? 'Billable (off — rework)' : 'Billable'}
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
          placeholder={
            commentRequiredForPostCompletion
              ? 'Required: explain rework, customer change, or internal correction…'
              : 'Optional notes…'
          }
          required={commentRequiredForPostCompletion}
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
          disabled={readOnly || saving || postCompletionBlocked}
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

      {selectedTool?.kind === 'project' && selectedProject ? (
        <TimesheetProjectContextPanel projectId={selectedProject.id} />
      ) : null}

      {dailyWarning ? (
        <Alert severity="warning" sx={{ mt: 1, py: 0 }}>
          Daily total would reach {projectedDailyTotal.toFixed(1)} hours (limit {dailyLimit}).
        </Alert>
      ) : null}
    </Box>
  );
}
