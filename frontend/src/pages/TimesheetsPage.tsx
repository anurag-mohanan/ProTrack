import { useCallback, useMemo, useState } from 'react';
import { Alert, Box, Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import {
  TimesheetEntryForm,
  type TimesheetEntryFormValues,
} from '../components/timesheets/TimesheetEntryForm';
import { TimesheetEntriesTable } from '../components/timesheets/TimesheetEntriesTable';
import { TimesheetMonthNavigation } from '../components/timesheets/TimesheetMonthNavigation';
import { TimesheetMonthSummaryBar } from '../components/timesheets/TimesheetMonthSummaryBar';
import { TimesheetNpReferencePanel } from '../components/timesheets/TimesheetNpReferencePanel';
import { TimesheetQuickActions } from '../components/timesheets/TimesheetQuickActions';
import {
  TimesheetUsersOverview,
  type TimesheetOverviewSection,
} from '../components/timesheets/TimesheetUsersOverview';
import { toolOptionFromEntry } from '../components/timesheets/timesheetToolOptions';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useTimesheetMonthWorkspace } from '../hooks/useTimesheetMonthWorkspace';
import type { TimesheetEntry } from '../types';
import {
  canApproveTimesheet,
  canEnterOwnTimesheet,
  canOverrideBillable,
  canRejectTimesheet,
  canReturnToDraft,
  canSubmitTimesheet,
  canViewAllTimesheets,
  isAdminRole,
  isReadOnlyRole,
} from '../utils/permissions';
import { currentMonthValue, formatMonthLabel, todayIsoDate } from '../utils/timesheetMonth';
import { formatDisplayValue, userDisplayName } from '../utils/format';

function shiftIsoDate(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T12:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export function TimesheetsPage() {
  const { user } = useAuth();
  const { showError, showSuccess } = useToast();
  const [monthValue, setMonthValue] = useState(currentMonthValue());
  const [editingEntry, setEditingEntry] = useState<TimesheetEntry | null>(null);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [deletingEntryId, setDeletingEntryId] = useState<string | null>(null);
  const [toolbarDate, setToolbarDate] = useState(todayIsoDate());

  const roleName = user?.role_name ?? '';
  const canViewAll = user ? canViewAllTimesheets(user) : false;
  const canEnterOwn = user ? canEnterOwnTimesheet(user) : true;
  // System admins (who cannot enter their own) always land on the all-users
  // overview. Managers who can view all but also log time default to "mine".
  const [viewMode, setViewMode] = useState<'mine' | 'all'>(
    !canEnterOwn && canViewAll ? 'all' : 'mine',
  );
  const viewAllUsers = canViewAll && viewMode === 'all';

  const workspace = useTimesheetMonthWorkspace(user, monthValue, viewAllUsers);
  const monthLabel = formatMonthLabel(monthValue);

  const showEntryForm = canEnterOwn && !viewAllUsers;

  const readOnly =
    viewAllUsers ||
    isReadOnlyRole(roleName) ||
    workspace.monthStatus === 'approved' ||
    workspace.monthStatus === 'submitted';

  const selectedEntry =
    workspace.entries.find((entry) => entry.id === selectedEntryId) ?? null;

  const isAdmin = isAdminRole(roleName);

  const entriesByUser = useMemo(() => {
    const map = new Map<string, TimesheetEntry[]>();
    for (const entry of workspace.entries) {
      const key = entry.user_id ?? 'unknown';
      const list = map.get(key);
      if (list) list.push(entry);
      else map.set(key, [entry]);
    }
    return map;
  }, [workspace.entries]);

  const overviewSections = useMemo<TimesheetOverviewSection[]>(() => {
    if (!viewAllUsers) return [];
    const fullName = (person: (typeof workspace.allUsers)[number]) =>
      `${person.first_name} ${person.last_name}`.trim();
    const activeUsers = workspace.allUsers
      .filter((person) => person.is_active !== false)
      .sort((left, right) => fullName(left).localeCompare(fullName(right)));
    const toOverview = (person: (typeof workspace.allUsers)[number]) => ({
      id: person.id,
      name: fullName(person),
    });

    if (isAdmin) {
      return [
        {
          title: 'All Users',
          emptyText: 'No users found',
          users: activeUsers.map(toOverview),
        },
      ];
    }

    const selfRecord = workspace.allUsers.find((person) => person.id === user?.id);
    const selfTeamId = selfRecord?.team_id ?? null;
    const selfUsers = activeUsers.filter((person) => person.id === user?.id);
    const teamUsers = activeUsers.filter(
      (person) =>
        person.id !== user?.id && selfTeamId != null && person.team_id === selfTeamId,
    );

    return [
      { title: 'My Timesheets', users: selfUsers.map(toOverview) },
      {
        title: 'Team Timesheets',
        emptyText: 'No team members assigned to your team',
        users: teamUsers.map(toOverview),
      },
    ];
  }, [viewAllUsers, workspace.allUsers, isAdmin, user?.id]);

  const saveEntryPayload = useCallback(
    (values: TimesheetEntryFormValues, entryId?: string | null) => ({
      entryId: entryId ?? null,
      entryDate: values.entryDate,
      toolValue: values.toolValue,
      taskTypeId: values.taskTypeId || null,
      hours: Number(values.hours),
      notes: values.notes,
      isBillable: values.isBillable,
    }),
    [],
  );

  const handleSaveEntry = async (values: TimesheetEntryFormValues) => {
    const hours = Number(values.hours);
    if (!values.entryDate || !Number.isFinite(hours) || hours <= 0) {
      showError('Enter a valid date and hours.');
      throw new Error('Invalid entry');
    }
    if (!values.toolValue) {
      showError('Select a tool number or NP code.');
      throw new Error('Invalid entry');
    }
    if (values.toolValue.startsWith('project:') && !values.taskTypeId) {
      showError('Select a task for project work.');
      throw new Error('Invalid entry');
    }

    try {
      await workspace.saveEntryMutation.mutateAsync(
        saveEntryPayload(values, editingEntry?.id),
      );
      showSuccess(editingEntry ? 'Entry updated.' : 'Entry added.');
      setEditingEntry(null);
      setSelectedEntryId(null);
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Unable to save entry.');
      throw error;
    }
  };

  const handleDeleteEntry = async (entry: TimesheetEntry) => {
    setDeletingEntryId(entry.id);
    try {
      await workspace.deleteEntryMutation.mutateAsync(entry.id);
      if (editingEntry?.id === entry.id) setEditingEntry(null);
      if (selectedEntryId === entry.id) setSelectedEntryId(null);
      showSuccess('Entry deleted.');
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Unable to delete entry.');
    } finally {
      setDeletingEntryId(null);
    }
  };

  const copyEntriesFromDate = async (sourceDate: string, label: string) => {
    const sources = workspace.entries.filter(
      (entry) => entry.entry_date === sourceDate && workspace.isEntryEditable(entry),
    );
    if (!sources.length) {
      showError(`No editable entries found for ${label}.`);
      return;
    }

    try {
      for (const entry of sources) {
        await workspace.saveEntryMutation.mutateAsync({
          entryDate: toolbarDate,
          toolValue: toolOptionFromEntry(entry),
          taskTypeId: entry.task_type_id,
          hours: Number(entry.hours),
          notes: entry.description ?? '',
          isBillable: entry.is_billable,
        });
      }
      showSuccess(`Copied ${sources.length} ${sources.length === 1 ? 'entry' : 'entries'}.`);
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Copy failed.');
    }
  };

  const handleCopyYesterday = () => {
    void copyEntriesFromDate(shiftIsoDate(toolbarDate, -1), 'yesterday');
  };

  const handleCopyPreviousWeek = () => {
    void copyEntriesFromDate(shiftIsoDate(toolbarDate, -7), 'the previous week');
  };

  const handleDuplicateSelected = async () => {
    if (!selectedEntry || !workspace.isEntryEditable(selectedEntry)) {
      showError('Select an editable entry to duplicate.');
      return;
    }
    try {
      await workspace.saveEntryMutation.mutateAsync({
        entryDate: selectedEntry.entry_date,
        toolValue: toolOptionFromEntry(selectedEntry),
        taskTypeId: selectedEntry.task_type_id,
        hours: Number(selectedEntry.hours),
        notes: selectedEntry.description ?? '',
        isBillable: selectedEntry.is_billable,
      });
      showSuccess('Entry duplicated.');
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Duplicate failed.');
    }
  };

  const handleSubmitMonth = async () => {
    try {
      await workspace.submitMonthMutation.mutateAsync();
      showSuccess('Timesheet submitted for approval.');
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Submit failed.');
    }
  };

  if (workspace.isLoading) {
    return <LoadingState message="Loading timesheet workspace…" />;
  }

  if (workspace.error) {
    console.error('Timesheet workspace failed to load lookup data:', workspace.error);
    return (
      <ErrorState
        error={workspace.error}
        title="Unable to load lookup data"
        onRetry={workspace.refetchLookups}
      />
    );
  }

  const showSubmit =
    user &&
    !readOnly &&
    workspace.draftTimesheets.some((sheet) =>
      workspace.entries.some((entry) => entry.timesheet_id === sheet.id),
    ) &&
    canSubmitTimesheet('draft', user.id, user.id, roleName);

  const reviewableTimesheets = workspace.timesheets.filter(
    (sheet) => sheet.status === 'submitted',
  );

  const quickActionLoading = workspace.saveEntryMutation.isPending;

  return (
    <PageContainer>
      <PageHeader
        subtitle={`${formatDisplayValue(user ? userDisplayName(user) : '')} · Monthly timesheet workspace`}
        action={
          showSubmit ? (
            <ProsohmButton
              buttonVariant="primary"
              loading={workspace.submitMonthMutation.isPending}
              onClick={() => void handleSubmitMonth()}
            >
              Submit Timesheet
            </ProsohmButton>
          ) : undefined
        }
      />

      <TimesheetMonthNavigation monthValue={monthValue} onMonthChange={setMonthValue} />

      {canViewAll && canEnterOwn ? (
        <ToggleButtonGroup
          size="small"
          exclusive
          value={viewMode}
          onChange={(_, next) => {
            if (next) setViewMode(next);
          }}
          sx={{ mb: 1.5 }}
        >
          <ToggleButton value="mine">My Entries</ToggleButton>
          <ToggleButton value="all">All Users</ToggleButton>
        </ToggleButtonGroup>
      ) : null}

      <TimesheetMonthSummaryBar status={workspace.monthStatus} summary={workspace.summary} />

      {workspace.summary.remainingHours < 0 ? (
        <Alert severity="warning" sx={{ mb: 1.5 }}>
          Entered hours exceed expected hours for this month.
        </Alert>
      ) : null}

      {showEntryForm ? <TimesheetNpReferencePanel codes={workspace.npCodes} /> : null}

      {showEntryForm ? (
        <TimesheetEntryForm
          projects={workspace.activeProjects}
          npCodes={workspace.npCodes}
          taskTypes={workspace.taskTypes}
          readOnly={readOnly}
          canOverrideBillable={canOverrideBillable(roleName)}
          editingEntry={editingEntry}
          dailyTotals={workspace.dailyTotals}
          dailyLimit={workspace.dailyLimit}
          saving={workspace.saveEntryMutation.isPending}
          onSubmit={handleSaveEntry}
          onCancelEdit={() => setEditingEntry(null)}
          onEntryDateChange={setToolbarDate}
        />
      ) : null}

      {showEntryForm ? (
        <TimesheetQuickActions
          readOnly={readOnly}
          loading={quickActionLoading}
          hasSelectedEntry={Boolean(selectedEntry && workspace.isEntryEditable(selectedEntry))}
          onCopyYesterday={handleCopyYesterday}
          onCopyPreviousWeek={handleCopyPreviousWeek}
          onDuplicateSelected={() => void handleDuplicateSelected()}
        />
      ) : null}

      {viewAllUsers ? (
        <>
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
            Timesheets for {monthLabel}
          </Typography>
          <TimesheetUsersOverview
            sections={overviewSections}
            entriesByUser={entriesByUser}
            timesheetById={workspace.timesheetById}
          />
        </>
      ) : (
        <TimesheetEntriesTable
          monthLabel={monthLabel}
          entries={workspace.entries}
          timesheetById={workspace.timesheetById}
          dailyTotals={workspace.dailyTotals}
          dailyLimit={workspace.dailyLimit}
          readOnly={readOnly}
          showUser={viewAllUsers}
          deletingId={deletingEntryId}
          selectedEntryId={selectedEntryId}
          onSelect={(entry) => setSelectedEntryId(entry?.id ?? null)}
          onEdit={setEditingEntry}
          onDelete={(entry) => void handleDeleteEntry(entry)}
          isEntryEditable={workspace.isEntryEditable}
        />
      )}

      {reviewableTimesheets.length ? (
        <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: 'wrap' }}>
          {reviewableTimesheets.map((sheet) => (
            <Box key={sheet.id} sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {canApproveTimesheet(sheet.status, roleName) ? (
                <ProsohmButton
                  size="small"
                  onClick={() =>
                    void workspace.workflowMutation
                      .mutateAsync({ action: 'approve', timesheetId: sheet.id })
                      .then(() => showSuccess('Timesheet approved.'))
                      .catch((error) =>
                        showError(error instanceof Error ? error.message : 'Approve failed'),
                      )
                  }
                >
                  Approve Week {sheet.week_start}
                </ProsohmButton>
              ) : null}
              {canRejectTimesheet(sheet.status, roleName) ? (
                <ProsohmButton
                  buttonVariant="outlined"
                  size="small"
                  onClick={() =>
                    void workspace.workflowMutation
                      .mutateAsync({ action: 'reject', timesheetId: sheet.id })
                      .then(() => showSuccess('Timesheet rejected.'))
                      .catch((error) =>
                        showError(error instanceof Error ? error.message : 'Reject failed'),
                      )
                  }
                >
                  Reject Week {sheet.week_start}
                </ProsohmButton>
              ) : null}
              {user &&
              canReturnToDraft(sheet.status, sheet.user_id, user.id, roleName) ? (
                <ProsohmButton
                  buttonVariant="outlined"
                  size="small"
                  onClick={() =>
                    void workspace.workflowMutation
                      .mutateAsync({ action: 'return', timesheetId: sheet.id })
                      .then(() => showSuccess('Returned to draft.'))
                      .catch((error) =>
                        showError(error instanceof Error ? error.message : 'Return failed'),
                      )
                  }
                >
                  Return Week {sheet.week_start}
                </ProsohmButton>
              ) : null}
            </Box>
          ))}
        </Stack>
      ) : null}
    </PageContainer>
  );
}
