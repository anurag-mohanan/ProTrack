import { useState } from 'react';
import { Alert, Box, Grid, Stack } from '@mui/material';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { TimesheetEntryForm, type TimesheetEntryFormValues } from '../components/timesheets/TimesheetEntryForm';
import { TimesheetEntriesTable } from '../components/timesheets/TimesheetEntriesTable';
import { TimesheetMonthNavigation } from '../components/timesheets/TimesheetMonthNavigation';
import { TimesheetMonthSummaryBar } from '../components/timesheets/TimesheetMonthSummaryBar';
import { TimesheetNpReferencePanel } from '../components/timesheets/TimesheetNpReferencePanel';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useTimesheetMonthWorkspace } from '../hooks/useTimesheetMonthWorkspace';
import type { TimesheetEntry } from '../types';
import {
  canApproveTimesheet,
  canRejectTimesheet,
  canReturnToDraft,
  canSubmitTimesheet,
  isReadOnlyRole,
} from '../utils/permissions';
import { currentMonthValue, formatMonthLabel } from '../utils/timesheetMonth';
import { formatDisplayValue, userDisplayName } from '../utils/format';

export function TimesheetsPage() {
  const { user } = useAuth();
  const { showError, showSuccess } = useToast();
  const [monthValue, setMonthValue] = useState(currentMonthValue());
  const [editingEntry, setEditingEntry] = useState<TimesheetEntry | null>(null);
  const [deletingEntryId, setDeletingEntryId] = useState<string | null>(null);

  const workspace = useTimesheetMonthWorkspace(user, monthValue);
  const monthLabel = formatMonthLabel(monthValue);
  const roleName = user?.role_name ?? '';

  const readOnly =
    isReadOnlyRole(roleName) ||
    workspace.monthStatus === 'approved' ||
    workspace.monthStatus === 'submitted';

  const handleSaveEntry = async (values: TimesheetEntryFormValues) => {
    const hours = Number(values.hours);
    if (!values.entryDate || !Number.isFinite(hours) || hours <= 0) {
      showError('Enter a valid date and hours.');
      return;
    }
    if (!values.toolValue) {
      showError('Select a tool number or NP code.');
      return;
    }
    if (values.toolValue.startsWith('project:') && !values.taskTypeId) {
      showError('Select a task for project work.');
      return;
    }

    try {
      await workspace.saveEntryMutation.mutateAsync({
        entryId: editingEntry?.id,
        entryDate: values.entryDate,
        toolValue: values.toolValue,
        taskTypeId: values.taskTypeId || null,
        hours,
        notes: values.notes,
      });
      showSuccess(editingEntry ? 'Entry updated.' : 'Entry added.');
      setEditingEntry(null);
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Unable to save entry.');
    }
  };

  const handleDeleteEntry = async (entry: TimesheetEntry) => {
    setDeletingEntryId(entry.id);
    try {
      await workspace.deleteEntryMutation.mutateAsync(entry.id);
      if (editingEntry?.id === entry.id) setEditingEntry(null);
      showSuccess('Entry deleted.');
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Unable to delete entry.');
    } finally {
      setDeletingEntryId(null);
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
    return <ErrorState error={workspace.error} />;
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

      <TimesheetMonthNavigation monthValue={monthValue} onMonthChange={setMonthValue} />

      <TimesheetMonthSummaryBar
        monthLabel={monthLabel}
        status={workspace.monthStatus}
        summary={workspace.summary}
      />

      {workspace.summary.remainingHours < 0 ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Entered hours exceed expected hours for this month.
        </Alert>
      ) : null}

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 9 }}>
          <TimesheetEntryForm
            monthLabel={monthLabel}
            projects={workspace.activeProjects}
            npCodes={workspace.npCodes}
            taskTypes={workspace.taskTypes}
            readOnly={readOnly}
            editingEntry={editingEntry}
            dailyTotals={workspace.dailyTotals}
            dailyLimit={workspace.dailyLimit}
            saving={workspace.saveEntryMutation.isPending}
            onSubmit={handleSaveEntry}
            onCancelEdit={() => setEditingEntry(null)}
          />

          <TimesheetEntriesTable
            monthLabel={monthLabel}
            entries={workspace.entries}
            timesheetById={workspace.timesheetById}
            dailyTotals={workspace.dailyTotals}
            dailyLimit={workspace.dailyLimit}
            readOnly={readOnly}
            deletingId={deletingEntryId}
            onEdit={setEditingEntry}
            onDelete={(entry) => void handleDeleteEntry(entry)}
            isEntryEditable={workspace.isEntryEditable}
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
        </Grid>

        <Grid size={{ xs: 12, lg: 3 }}>
          <TimesheetNpReferencePanel codes={workspace.npCodes} />
        </Grid>
      </Grid>
    </PageContainer>
  );
}
