import { useCallback, useMemo, useState } from 'react';
import { Alert, Box, Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { StickyRecordHeader } from '../components/ui/design-system';
import { APP_TOP_BAR_OFFSET } from '../components/ui/design-system/StickyRecordHeader';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { TimesheetEntryForm, type TimesheetEntryFormValues } from '../components/timesheets/TimesheetEntryForm';
import { TimesheetEntryEditDialog } from '../components/timesheets/TimesheetEntryEditDialog';
import { TimesheetEntryDeleteDialog } from '../components/timesheets/TimesheetEntryDeleteDialog';
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
import {
  currentMonthValue,
  formatLocalIso,
  formatMonthLabel,
  isWeekend,
  sumEntryHours,
  todayIsoDate,
  weekStartMonday,
  weekWorkingDayCount,
} from '../utils/timesheetMonth';
import {
  buildScopedOverviewSummary,
  buildTeamTimesheetSections,
  buildTodayScopedSummary,
  buildWeeklyScopedSummary,
  teamSectionBreakdownLabel,
} from '../utils/timesheetOverview';
import { isTimesheetMonthCalendarLocked } from '../utils/timesheetLocking';
import { formatDisplayValue, userDisplayName } from '../utils/format';
import { TimesheetStatusBadge } from '../components/ui/design-system';

function shiftIsoDate(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T12:00:00`);
  date.setDate(date.getDate() + days);
  return formatLocalIso(date);
}

export function TimesheetsPage() {
  const { user } = useAuth();
  const { showError, showSuccess } = useToast();
  const [monthValue, setMonthValue] = useState(currentMonthValue());
  const [editDialogEntry, setEditDialogEntry] = useState<TimesheetEntry | null>(null);
  const [deleteDialogEntry, setDeleteDialogEntry] = useState<TimesheetEntry | null>(null);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [deletingEntryId, setDeletingEntryId] = useState<string | null>(null);
  const [toolbarDate, setToolbarDate] = useState(todayIsoDate());

  const roleName = user?.role_name ?? '';
  const isAdmin = isAdminRole(roleName);
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

  const calendarLocked = isTimesheetMonthCalendarLocked(monthValue, {
    adminOverride: isAdmin,
  });

  // Editability depends only on the calendar rule (current + previous two
  // months) and role. Workflow status does NOT lock the timesheet.
  const readOnly = viewAllUsers || isReadOnlyRole(roleName) || calendarLocked;

  const selectedEntry =
    workspace.entries.find((entry) => entry.id === selectedEntryId) ?? null;

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
    if (!viewAllUsers || !workspace.overviewContext) return [];

    const teamSections = buildTeamTimesheetSections(
      workspace.overviewContext.teams,
      workspace.overviewContext.users,
      workspace.entries,
      workspace.workingDayCount,
    );

    return teamSections.map((section) => ({
      title: section.teamName,
      subtitle: teamSectionBreakdownLabel(section.summary),
      emptyText: 'No team members with entries this month',
      users: section.users.map((person) => ({
        id: person.id,
        name: `${person.first_name} ${person.last_name}`.trim(),
      })),
    }));
  }, [
    viewAllUsers,
    workspace.overviewContext,
    workspace.entries,
    workspace.workingDayCount,
  ]);

  const scopedOverviewUsers = workspace.overviewContext?.users ?? [];

  const overviewSummary = useMemo(() => {
    if (!viewAllUsers || !scopedOverviewUsers.length) return workspace.summary;
    return buildScopedOverviewSummary(
      scopedOverviewUsers,
      workspace.entries,
      workspace.workingDayCount,
    );
  }, [
    viewAllUsers,
    scopedOverviewUsers,
    workspace.entries,
    workspace.workingDayCount,
    workspace.summary,
  ]);

  const saveEntryPayload = useCallback(
    (values: TimesheetEntryFormValues, entryId?: string | null) => ({
      entryId: entryId ?? null,
      entryDate: values.entryDate,
      toolValue: values.toolValue,
      taskTypeId: values.taskTypeId || null,
      hours: Number(values.hours),
      notes: values.notes,
      isBillable: values.isBillable,
      contributionReason: values.contributionReason || null,
    }),
    [],
  );

  const handleSaveEntry = async (values: TimesheetEntryFormValues, entryId?: string | null) => {
    const hours = Number(values.hours);
    const isProjectWork = values.toolValue.startsWith('project:');
    if (!values.entryDate || !Number.isFinite(hours) || hours < 0 || hours > 24) {
      showError('Enter a valid date and hours.');
      throw new Error('Invalid entry');
    }
    if (isProjectWork && hours <= 0) {
      showError('Project work must be greater than 0 hours.');
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
        saveEntryPayload(values, entryId),
      );
      showSuccess(entryId ? 'Entry updated.' : 'Entry added.');
      setEditDialogEntry(null);
      setSelectedEntryId(null);
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Unable to save entry.');
      throw error;
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteDialogEntry) return;
    setDeletingEntryId(deleteDialogEntry.id);
    try {
      await workspace.deleteEntryMutation.mutateAsync(deleteDialogEntry.id);
      if (editDialogEntry?.id === deleteDialogEntry.id) setEditDialogEntry(null);
      if (selectedEntryId === deleteDialogEntry.id) setSelectedEntryId(null);
      showSuccess('Entry deleted.');
      setDeleteDialogEntry(null);
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
          contributionReason: entry.contribution_reason ?? null,
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
        contributionReason: selectedEntry.contribution_reason ?? null,
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

  const quickActionLoading = workspace.saveEntryMutation.isPending;

  const handleDuplicateEntry = async (entry: TimesheetEntry) => {
    if (!workspace.isEntryEditable(entry)) {
      showError('This entry cannot be duplicated.');
      return;
    }
    try {
      await workspace.saveEntryMutation.mutateAsync({
        entryDate: entry.entry_date,
        toolValue: toolOptionFromEntry(entry),
        taskTypeId: entry.task_type_id,
        hours: Number(entry.hours),
        notes: entry.description ?? '',
        isBillable: entry.is_billable,
        contributionReason: entry.contribution_reason ?? null,
      });
      showSuccess('Entry duplicated.');
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Duplicate failed.');
    }
  };

  const todayIso = todayIsoDate();
  const todayScoped = useMemo(() => {
    if (!viewAllUsers || !scopedOverviewUsers.length) {
      return {
        todayHours: sumEntryHours(workspace.entries.filter((e) => e.entry_date === todayIso)),
        todayExpected:
          isWeekend(todayIso) || workspace.holidayDates.has(todayIso) ? 0 : workspace.dailyLimit,
      };
    }
    return buildTodayScopedSummary(
      scopedOverviewUsers,
      workspace.entries,
      todayIso,
      workspace.holidayDates,
    );
  }, [
    viewAllUsers,
    scopedOverviewUsers,
    workspace.entries,
    workspace.holidayDates,
    workspace.dailyLimit,
    todayIso,
  ]);
  const todayHours = todayScoped.todayHours;
  const todayExpected = todayScoped.todayExpected;

  const weeklyScoped = useMemo(() => {
    const weekStart = weekStartMonday(toolbarDate);
    const weekEnd = shiftIsoDate(weekStart, 6);
    if (!viewAllUsers || !scopedOverviewUsers.length) {
      const hours = sumEntryHours(
        workspace.entries.filter((e) => e.entry_date >= weekStart && e.entry_date <= weekEnd),
      );
      const workingDays = weekWorkingDayCount(toolbarDate, workspace.holidayDates);
      return { weeklyHours: hours, weeklyExpected: workingDays * workspace.dailyLimit };
    }
    return buildWeeklyScopedSummary(
      scopedOverviewUsers,
      workspace.entries,
      weekStart,
      weekEnd,
      workspace.holidayDates,
      toolbarDate,
    );
  }, [
    viewAllUsers,
    scopedOverviewUsers,
    workspace.entries,
    toolbarDate,
    workspace.holidayDates,
    workspace.dailyLimit,
  ]);
  const weeklyHours = weeklyScoped.weeklyHours;
  const weeklyExpected = weeklyScoped.weeklyExpected;

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

      <StickyRecordHeader
        compact
        primaryLabel={monthLabel}
        secondaryLabel={
          viewAllUsers
            ? workspace.overviewContext?.scope_all_teams
              ? 'All teams — timesheet overview'
              : 'Your teams — timesheet overview'
            : `${formatDisplayValue(user ? userDisplayName(user) : '')} · ${toolbarDate}`
        }
        stickyTop={APP_TOP_BAR_OFFSET}
        meta={<TimesheetStatusBadge status={workspace.monthStatus} />}
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

      <TimesheetMonthSummaryBar
        status={workspace.monthStatus}
        summary={viewAllUsers ? overviewSummary : workspace.summary}
        todayHours={todayHours}
        todayExpected={todayExpected}
        weeklyHours={weeklyHours}
        weeklyExpected={weeklyExpected}
        scopeLabel={viewAllUsers ? 'Team rollup' : undefined}
      />

      {viewAllUsers && overviewSummary.remainingHours < 0 ? (
        <Alert severity="warning" sx={{ mb: 1.5 }}>
          Team entered hours exceed expected hours for this month.
        </Alert>
      ) : null}

      {!viewAllUsers && calendarLocked ? (
        <Alert severity="info" sx={{ mb: 1.5 }}>
          {isAdmin
            ? 'This timesheet is archived because it is older than two months. As a System Administrator you can still edit it.'
            : 'This timesheet is archived because it is older than two months.'}
        </Alert>
      ) : null}

      {!viewAllUsers &&
      !calendarLocked &&
      (workspace.monthStatus === 'approved' || workspace.monthStatus === 'submitted') ? (
        <Alert severity="success" sx={{ mb: 1.5 }}>
          {workspace.monthStatus === 'approved' ? 'Approved. ' : 'Submitted. '}
          You may still edit this month&apos;s entries. Changes will automatically update
          approvals.
        </Alert>
      ) : null}

      {!viewAllUsers && workspace.summary.remainingHours < 0 ? (
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
          editingEntry={null}
          dailyTotals={workspace.dailyTotals}
          dailyLimit={workspace.dailyLimit}
          saving={workspace.saveEntryMutation.isPending}
          currentUserId={user?.id}
          onProjectSearch={workspace.setProjectSearch}
          onSubmit={(values) => handleSaveEntry(values)}
          onCancelEdit={() => undefined}
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
          onEdit={setEditDialogEntry}
          onDelete={setDeleteDialogEntry}
          onDuplicate={(entry) => void handleDuplicateEntry(entry)}
          isEntryEditable={workspace.isEntryEditable}
          onRequestDeleteSelected={() => {
            if (selectedEntry && workspace.isEntryEditable(selectedEntry) && !readOnly) {
              setDeleteDialogEntry(selectedEntry);
            }
          }}
        />
      )}

      <TimesheetEntryEditDialog
        open={Boolean(editDialogEntry)}
        entry={editDialogEntry}
        projects={workspace.activeProjects}
        npCodes={workspace.npCodes}
        taskTypes={workspace.taskTypes}
        canOverrideBillable={canOverrideBillable(roleName)}
        dailyTotals={workspace.dailyTotals}
        dailyLimit={workspace.dailyLimit}
        saving={workspace.saveEntryMutation.isPending}
        currentUserId={user?.id}
        onProjectSearch={workspace.setProjectSearch}
        onSave={(values) => handleSaveEntry(values, editDialogEntry?.id)}
        onClose={() => setEditDialogEntry(null)}
      />

      <TimesheetEntryDeleteDialog
        open={Boolean(deleteDialogEntry)}
        entry={deleteDialogEntry}
        loading={Boolean(deletingEntryId)}
        onCancel={() => setDeleteDialogEntry(null)}
        onConfirm={() => void handleConfirmDelete()}
      />

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
