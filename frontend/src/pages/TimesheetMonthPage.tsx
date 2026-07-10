import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  Grid,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchHolidays } from '../api/settings';
import { fetchTaskTypes, fetchTimesheetProjects } from '../api/lookups';
import {
  bulkSaveTimesheetEntries,
  ensureWeekTimesheet,
  fetchTimesheetEntries,
  fetchTimesheets,
} from '../api/timesheets';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { TimesheetStatusChip } from '../components/common/StatusChip';
import {
  createBlankRow,
  entryToGridRow,
  formatHoursTotal,
  buildMonthGridRows,
  summarizeDailyHours,
  summarizeHours,
  TimesheetMonthGrid,
  type TimesheetGridRow,
} from '../components/timesheets/TimesheetMonthGrid';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import {
  approveTimesheet,
  rejectTimesheet,
  returnTimesheetToDraft,
  submitTimesheet,
  timesheetQueryKeys,
} from '../services/timesheetService';
import type { Timesheet, TimesheetEntry } from '../types';
import {
  canApproveTimesheet,
  canRejectTimesheet,
  canReturnToDraft,
  canSubmitTimesheet,
  isAdminRole,
} from '../utils/permissions';
import { isTimesheetMonthCalendarLocked } from '../utils/timesheetLocking';
import {
  countWorkingDays,
  formatMonthLabel,
  isWeekend,
  monthBounds,
  weekStartMonday,
} from '../utils/timesheetMonth';
import { formatDisplayValue, userDisplayName } from '../utils/format';
import { invalidateTimesheetRelatedQueries } from '../utils/queryInvalidation';

function currentMonthValue(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}


export function TimesheetMonthPage() {
  const { user } = useAuth();
  const { showError, showSuccess } = useToast();
  const queryClient = useQueryClient();
  const [monthValue, setMonthValue] = useState(currentMonthValue());
  const [rows, setRows] = useState<TimesheetGridRow[]>([]);
  const [selectedTimesheetId, setSelectedTimesheetId] = useState<string | null>(null);
  const historyRef = useRef<{ past: TimesheetGridRow[][]; future: TimesheetGridRow[][] }>({
    past: [],
    future: [],
  });

  const setRowsWithHistory = useCallback((updater: TimesheetGridRow[] | ((current: TimesheetGridRow[]) => TimesheetGridRow[])) => {
    setRows((current) => {
      const next = typeof updater === 'function' ? updater(current) : updater;
      if (next !== current) {
        historyRef.current.past.push(current);
        if (historyRef.current.past.length > 50) {
          historyRef.current.past.shift();
        }
        historyRef.current.future = [];
      }
      return next;
    });
  }, []);

  const bounds = useMemo(() => monthBounds(monthValue), [monthValue]);

  const holidaysQuery = useQuery({
    queryKey: ['settings', 'holidays'],
    queryFn: fetchHolidays,
  });

  const projectsQuery = useQuery({
    queryKey: ['timesheet-projects'],
    queryFn: fetchTimesheetProjects,
  });

  const taskTypesQuery = useQuery({
    queryKey: ['task-types', 'all'],
    queryFn: () => fetchTaskTypes(),
  });

  const timesheetsQuery = useQuery({
    queryKey: [...timesheetQueryKeys.all, monthValue, user?.id],
    queryFn: () =>
      fetchTimesheets({
        user_id: user?.id,
        month: monthValue,
        limit: 20,
      }),
    enabled: Boolean(user?.id),
  });

  const entriesQuery = useQuery({
    queryKey: ['timesheet-entries', monthValue, user?.id],
    queryFn: () =>
      fetchTimesheetEntries({
        user_id: user?.id,
        entry_date_from: bounds.start,
        entry_date_to: bounds.end,
        limit: 500,
      }),
    enabled: Boolean(user?.id),
  });

  const holidayDates = useMemo(
    () => new Set((holidaysQuery.data ?? []).map((holiday) => holiday.holiday_date)),
    [holidaysQuery.data],
  );

  const activeProjects = useMemo(
    () => projectsQuery.data ?? [],
    [projectsQuery.data],
  );

  const draftTimesheets = useMemo(
    () => (timesheetsQuery.data ?? []).filter((sheet) => sheet.status === 'draft'),
    [timesheetsQuery.data],
  );

  const primaryTimesheet: Timesheet | null = useMemo(() => {
    if (selectedTimesheetId) {
      return (timesheetsQuery.data ?? []).find((sheet) => sheet.id === selectedTimesheetId) ?? null;
    }
    return draftTimesheets[0] ?? (timesheetsQuery.data ?? [])[0] ?? null;
  }, [draftTimesheets, selectedTimesheetId, timesheetsQuery.data]);

  // Editability depends only on the calendar rule (current + previous two
  // months), not on workflow status.
  const readOnly = isTimesheetMonthCalendarLocked(monthValue, {
    adminOverride: isAdminRole(user?.role_name ?? ''),
  });

  useEffect(() => {
    if (!entriesQuery.data) return;
    historyRef.current = { past: [], future: [] };
    setRows(buildMonthGridRows(bounds.days, entriesQuery.data, readOnly, holidayDates));
  }, [bounds.days, entriesQuery.data, holidayDates, readOnly, monthValue]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || readOnly) return;
      if (event.key === 'z' && !event.shiftKey) {
        event.preventDefault();
        const previous = historyRef.current.past.pop();
        if (!previous) return;
        setRows((current) => {
          historyRef.current.future.push(current);
          return previous;
        });
      }
      if (event.key === 'y' || (event.key === 'z' && event.shiftKey)) {
        event.preventDefault();
        const next = historyRef.current.future.pop();
        if (!next) return;
        setRows((current) => {
          historyRef.current.past.push(current);
          return next;
        });
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [readOnly]);

  const workingDayCount = countWorkingDays(bounds.days, holidayDates);
  const dailyLimit = user?.working_hours_per_day ?? 8;
  const expectedHours = workingDayCount * dailyLimit;
  const enteredHours = summarizeHours(rows);
  const remainingHours = expectedHours - enteredHours;
  const dailyTotals = useMemo(() => summarizeDailyHours(rows), [rows]);
  const overLimitDays = useMemo(
    () =>
      [...dailyTotals.entries()].filter(
        ([date, total]) => !isWeekend(date) && !holidayDates.has(date) && total > dailyLimit,
      ),
    [dailyLimit, dailyTotals, holidayDates],
  );

  const saveRowMutation = useMutation({
    mutationFn: async (row: TimesheetGridRow): Promise<{ saved: TimesheetEntry; source: TimesheetGridRow }> => {
      if (!user?.id) throw new Error('Not authenticated');
      const hours = Number(row.hours);
      if (!row.entryDate || !Number.isFinite(hours) || hours <= 0 || hours > 24) {
        throw new Error('Enter a valid date and hours before saving.');
      }
      if (!row.projectId || !row.taskTypeId) {
        throw new Error('Select a tool number and task before saving.');
      }

      const weekStart = weekStartMonday(row.entryDate);
      const timesheet = await ensureWeekTimesheet({
        user_id: user.id,
        week_start: weekStart,
      });

      const payload = {
        id: row.entryId ?? null,
        timesheet_id: timesheet.id,
        work_category: 'productive' as const,
        project_id: row.projectId,
        task_type_id: row.taskTypeId,
        entry_date: row.entryDate,
        hours,
        is_billable: row.isBillable,
        description: row.notes || null,
      };

      const result = await bulkSaveTimesheetEntries({ upserts: [payload], deletes: [] });
      const saved = result.upserted[0];
      setSelectedTimesheetId(timesheet.id);
      invalidateTimesheetRelatedQueries(queryClient);
      return { saved, source: row };
    },
    onSuccess: ({ saved, source }) => {
      setRowsWithHistory((current) =>
        current.map((existing) =>
          existing.clientId === source.clientId
            ? {
                ...entryToGridRow(saved, saved.timesheet_id !== primaryTimesheet?.id && readOnly),
                clientId: source.clientId,
                isDirty: false,
              }
            : existing,
        ),
      );
      showSuccess('Timesheet row saved.');
    },
    onError: (error) => showError(error instanceof Error ? error.message : 'Save failed'),
  });

  const workflowMutation = useMutation({
    mutationFn: async (action: 'submit' | 'approve' | 'reject' | 'return') => {
      if (!primaryTimesheet) throw new Error('No timesheet selected');
      if (action === 'submit') return submitTimesheet(primaryTimesheet.id);
      if (action === 'approve') return approveTimesheet(primaryTimesheet.id);
      if (action === 'reject') return rejectTimesheet(primaryTimesheet.id, 'Rejected from monthly grid');
      return returnTimesheetToDraft(primaryTimesheet.id);
    },
    onSuccess: () => {
      invalidateTimesheetRelatedQueries(queryClient);
      showSuccess('Timesheet updated.');
    },
    onError: (error) => showError(error instanceof Error ? error.message : 'Workflow action failed'),
  });

  const handleCopyPreviousRow = useCallback(() => {
    if (rows.length < 2) return;
    const previous = rows[rows.length - 2];
    const last = rows[rows.length - 1];
    setRowsWithHistory((current) =>
      current.map((row) =>
        row.clientId === last.clientId
          ? {
              ...row,
              toolNumber: previous.toolNumber,
              projectId: previous.projectId,
              customerName: previous.customerName,
              taskTypeId: previous.taskTypeId,
              isBillable: previous.isBillable,
              isDirty: true,
            }
          : row,
      ),
    );
  }, [rows, setRowsWithHistory]);

  const handleAddRow = useCallback(() => {
    const lastDate = rows[rows.length - 1]?.entryDate ?? bounds.start;
    setRowsWithHistory((current) => [...current, createBlankRow(lastDate)]);
  }, [bounds.start, rows, setRowsWithHistory]);

  const roleName = user?.role_name ?? '';

  return (
    <PageContainer>
      <PageHeader
        subtitle={`${formatMonthLabel(monthValue)} · Excel-style monthly entry aligned with import template`}
        action={
          <TextField
            type="month"
            size="small"
            value={monthValue}
            onChange={(event) => setMonthValue(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
        }
      />

      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Box sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
            <Typography variant="caption" color="text.secondary">
              Designer
            </Typography>
            <Typography variant="h6">{formatDisplayValue(user ? userDisplayName(user) : '')}</Typography>
          </Box>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Box sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
            <Typography variant="caption" color="text.secondary">
              Working Days
            </Typography>
            <Typography variant="h6">{workingDayCount}</Typography>
          </Box>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 2 }}>
          <Box sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
            <Typography variant="caption" color="text.secondary">
              Expected
            </Typography>
            <Typography variant="h6">{formatHoursTotal(expectedHours)}</Typography>
          </Box>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 2 }}>
          <Box sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
            <Typography variant="caption" color="text.secondary">
              Entered
            </Typography>
            <Typography variant="h6">{formatHoursTotal(enteredHours)}</Typography>
          </Box>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 2 }}>
          <Box sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
            <Typography variant="caption" color="text.secondary">
              Remaining
            </Typography>
            <Typography variant="h6" color={remainingHours < 0 ? 'error.main' : 'text.primary'}>
              {formatHoursTotal(remainingHours)}
            </Typography>
          </Box>
        </Grid>
      </Grid>

      <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        {primaryTimesheet ? <TimesheetStatusChip status={primaryTimesheet.status} /> : null}
        <Chip label={`Month: ${formatMonthLabel(monthValue)}`} size="small" variant="outlined" />
        {!readOnly ? (
          <>
            <ProsohmButton buttonVariant="outlined" size="small" startIcon={<AddIcon />} onClick={handleAddRow}>
              Add Row
            </ProsohmButton>
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              startIcon={<ContentCopyIcon />}
              onClick={handleCopyPreviousRow}
            >
              Copy Previous Row
            </ProsohmButton>
          </>
        ) : null}
        {primaryTimesheet &&
        user &&
        canSubmitTimesheet(primaryTimesheet.status, primaryTimesheet.user_id, user.id, roleName) ? (
          <ProsohmButton size="small" onClick={() => workflowMutation.mutate('submit')}>
            Submit
          </ProsohmButton>
        ) : null}
        {primaryTimesheet && canApproveTimesheet(primaryTimesheet.status, roleName) ? (
          <ProsohmButton size="small" onClick={() => workflowMutation.mutate('approve')}>
            Approve
          </ProsohmButton>
        ) : null}
        {primaryTimesheet && canRejectTimesheet(primaryTimesheet.status, roleName) ? (
          <ProsohmButton
            buttonVariant="outlined"
            size="small"
            onClick={() => workflowMutation.mutate('reject')}
          >
            Reject
          </ProsohmButton>
        ) : null}
        {primaryTimesheet &&
        user &&
        canReturnToDraft(primaryTimesheet.status, primaryTimesheet.user_id, user.id, roleName) ? (
          <ProsohmButton
            buttonVariant="outlined"
            size="small"
            onClick={() => workflowMutation.mutate('return')}
          >
            Return to Draft
          </ProsohmButton>
        ) : null}
      </Stack>

      {remainingHours < 0 ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Entered hours exceed expected hours for this month.
        </Alert>
      ) : null}

      {overLimitDays.length ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Daily hours exceed {dailyLimit} on {overLimitDays.length} day
          {overLimitDays.length === 1 ? '' : 's'}.
        </Alert>
      ) : null}

      <TimesheetMonthGrid
        rows={rows}
        projects={activeProjects}
        taskTypes={taskTypesQuery.data ?? []}
        holidayDates={holidayDates}
        readOnly={readOnly}
        onRowsChange={setRowsWithHistory}
        onSaveRow={async (row) => {
          await saveRowMutation.mutateAsync(row);
        }}
      />
    </PageContainer>
  );
}
