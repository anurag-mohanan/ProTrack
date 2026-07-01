import { Fragment, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchTimesheetEntries } from '../api/timesheets';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { TimesheetStatusChip } from '../components/common/StatusChip';
import { PageHeader } from '../components/common/PageHeader';
import { useAuth } from '../context/AuthContext';
import {
  approveTimesheet,
  createTimesheet,
  getTimesheets,
  rejectTimesheet,
  returnTimesheetToDraft,
  submitTimesheet,
  timesheetQueryKeys,
} from '../services/timesheetService';
import { invalidateTimesheetRelatedQueries } from '../utils/queryInvalidation';
import {
  canApproveTimesheet,
  canRejectTimesheet,
  canReturnToDraft,
  canSubmitTimesheet,
  isReadOnlyRole,
} from '../utils/permissions';
import type { Timesheet } from '../types';
import { formatDate, formatNumber } from '../utils/format';

function weekStartMonday(date = new Date()): string {
  const copy = new Date(date);
  const day = copy.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  copy.setDate(copy.getDate() + diff);
  return copy.toISOString().slice(0, 10);
}

export function TimesheetsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [weekStart, setWeekStart] = useState(weekStartMonday());
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<Timesheet | null>(null);
  const [rejectComments, setRejectComments] = useState('');
  const [actionError, setActionError] = useState<unknown>(null);

  const timesheetsQuery = useQuery({
    queryKey: timesheetQueryKeys.all,
    queryFn: () => getTimesheets(),
  });

  const entriesQuery = useQuery({
    queryKey: timesheetQueryKeys.entries(expandedId ?? undefined),
    queryFn: () => fetchTimesheetEntries({ timesheet_id: expandedId ?? undefined }),
    enabled: Boolean(expandedId),
  });

  const invalidateTimesheets = (projectId?: string) => {
    invalidateTimesheetRelatedQueries(queryClient, projectId);
    if (expandedId) {
      void queryClient.invalidateQueries({
        queryKey: timesheetQueryKeys.entries(expandedId),
      });
    }
  };

  const createMutation = useMutation({
    mutationFn: createTimesheet,
    onSuccess: () => {
      invalidateTimesheets();
      setCreateOpen(false);
      setWeekStart(weekStartMonday());
    },
  });

  const workflowMutation = useMutation({
    mutationFn: async ({
      action,
      timesheetId,
      comments,
    }: {
      action: 'submit' | 'approve' | 'reject' | 'return';
      timesheetId: string;
      comments?: string;
    }) => {
      if (action === 'submit') return submitTimesheet(timesheetId);
      if (action === 'approve') return approveTimesheet(timesheetId, comments);
      if (action === 'reject') {
        if (!comments?.trim()) throw new Error('Comments are required when rejecting');
        return rejectTimesheet(timesheetId, comments.trim());
      }
      return returnTimesheetToDraft(timesheetId);
    },
    onSuccess: () => {
      setActionError(null);
      setRejectTarget(null);
      setRejectComments('');
      invalidateTimesheets();
    },
    onError: (error) => setActionError(error),
  });

  const sortedTimesheets = useMemo(
    () =>
      [...(timesheetsQuery.data ?? [])].sort((a, b) =>
        b.week_start.localeCompare(a.week_start),
      ),
    [timesheetsQuery.data],
  );

  const entryHoursByTimesheet = useMemo(() => {
    const map = new Map<string, number>();
    entriesQuery.data?.forEach((entry) => {
      map.set(entry.timesheet_id, (map.get(entry.timesheet_id) ?? 0) + Number(entry.hours));
    });
    return map;
  }, [entriesQuery.data]);

  if (timesheetsQuery.isLoading) return <LoadingState />;
  if (timesheetsQuery.error) return <ErrorState error={timesheetsQuery.error} />;

  const roleName = user?.role_name ?? '';

  return (
    <Box>
      <PageHeader
        title="Timesheets"
        subtitle="Weekly engineering timesheets"
        action={
          !isReadOnlyRole(roleName) ? (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setCreateOpen(true)}
              disabled={!user}
            >
              Create Timesheet
            </Button>
          ) : undefined
        }
      />

      {actionError ? (
        <Box sx={{ mb: 2 }}>
          <ErrorState error={actionError} title="Timesheet action failed" />
        </Box>
      ) : null}

      {!sortedTimesheets.length ? (
        <EmptyState
          title="No timesheets yet"
          description="Create a weekly timesheet to start logging time."
        />
      ) : (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Week Starting</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedTimesheets.map((timesheet) => {
                const isExpanded = expandedId === timesheet.id;
                const showSubmit = user
                  ? canSubmitTimesheet(
                      timesheet.status,
                      timesheet.user_id,
                      user.id,
                      roleName,
                    )
                  : false;
                const showReview = canApproveTimesheet(timesheet.status, roleName);
                const showReject = canRejectTimesheet(timesheet.status, roleName);
                const showReturn = user
                  ? canReturnToDraft(
                      timesheet.status,
                      timesheet.user_id,
                      user.id,
                      roleName,
                    )
                  : false;

                return (
                  <Fragment key={timesheet.id}>
                    <TableRow hover>
                      <TableCell>{formatDate(timesheet.week_start)}</TableCell>
                      <TableCell>
                        <TimesheetStatusChip status={timesheet.status} />
                      </TableCell>
                      <TableCell align="right">
                        <Stack
                          direction="row"
                          spacing={1}
                          sx={{ justifyContent: 'flex-end', flexWrap: 'wrap' }}
                        >
                          {showSubmit ? (
                            <Button
                              size="small"
                              variant="outlined"
                              disabled={workflowMutation.isPending}
                              onClick={() =>
                                workflowMutation.mutate({
                                  action: 'submit',
                                  timesheetId: timesheet.id,
                                })
                              }
                            >
                              Submit
                            </Button>
                          ) : null}
                          {showReview ? (
                            <Button
                              size="small"
                              color="success"
                              variant="outlined"
                              disabled={workflowMutation.isPending}
                              onClick={() =>
                                workflowMutation.mutate({
                                  action: 'approve',
                                  timesheetId: timesheet.id,
                                })
                              }
                            >
                              Approve
                            </Button>
                          ) : null}
                          {showReject ? (
                            <Button
                              size="small"
                              color="error"
                              variant="outlined"
                              disabled={workflowMutation.isPending}
                              onClick={() => setRejectTarget(timesheet)}
                            >
                              Reject
                            </Button>
                          ) : null}
                          {showReturn ? (
                            <Button
                              size="small"
                              variant="outlined"
                              disabled={workflowMutation.isPending}
                              onClick={() =>
                                workflowMutation.mutate({
                                  action: 'return',
                                  timesheetId: timesheet.id,
                                })
                              }
                            >
                              Return to Draft
                            </Button>
                          ) : null}
                          <Button
                            size="small"
                            onClick={() =>
                              setExpandedId(isExpanded ? null : timesheet.id)
                            }
                          >
                            {isExpanded ? 'Hide Entries' : 'View Entries'}
                          </Button>
                          {timesheet.status === 'draft' ? (
                            <Button
                              size="small"
                              component={Link}
                              to={`/timesheets/${timesheet.id}/entries/new`}
                            >
                              Add Entry
                            </Button>
                          ) : null}
                        </Stack>
                      </TableCell>
                    </TableRow>
                    {isExpanded ? (
                      <TableRow>
                        <TableCell colSpan={3} sx={{ bgcolor: 'background.default' }}>
                          {entriesQuery.isLoading ? (
                            <LoadingState message="Loading entries…" />
                          ) : entriesQuery.error ? (
                            <ErrorState error={entriesQuery.error} />
                          ) : !entriesQuery.data?.length ? (
                            <EmptyState
                              title="No entries"
                              description="Add a time entry for this week."
                            />
                          ) : (
                            <Table size="small">
                              <TableHead>
                                <TableRow>
                                  <TableCell>Date</TableCell>
                                  <TableCell>Category</TableCell>
                                  <TableCell>Project / NP Code</TableCell>
                                  <TableCell>Task</TableCell>
                                  <TableCell>Billable</TableCell>
                                  <TableCell align="right">Hours</TableCell>
                                  <TableCell>Notes</TableCell>
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {entriesQuery.data.map((entry) => (
                                  <TableRow key={entry.id}>
                                    <TableCell>{formatDate(entry.entry_date)}</TableCell>
                                    <TableCell>
                                      {entry.work_category === 'non_productive'
                                        ? 'Non-Productive'
                                        : 'Productive'}
                                    </TableCell>
                                    <TableCell>
                                      {entry.work_category === 'non_productive'
                                        ? entry.non_productive_code ?? '—'
                                        : entry.project_tool_number ?? '—'}
                                    </TableCell>
                                    <TableCell>{entry.task_type_name ?? '—'}</TableCell>
                                    <TableCell>{entry.is_billable ? 'Yes' : 'No'}</TableCell>
                                    <TableCell align="right">
                                      {formatNumber(entry.hours)}
                                    </TableCell>
                                    <TableCell>{entry.description ?? '—'}</TableCell>
                                  </TableRow>
                                ))}
                                <TableRow>
                                  <TableCell colSpan={5}>
                                    <strong>Total</strong>
                                  </TableCell>
                                  <TableCell align="right">
                                    <strong>
                                      {formatNumber(
                                        entryHoursByTimesheet.get(timesheet.id) ?? 0,
                                      )}
                                    </strong>
                                  </TableCell>
                                  <TableCell />
                                </TableRow>
                              </TableBody>
                            </Table>
                          )}
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Create Timesheet</DialogTitle>
        <DialogContent>
          <TextField
            label="Week Start"
            type="date"
            fullWidth
            margin="normal"
            slotProps={{ inputLabel: { shrink: true } }}
            value={weekStart}
            onChange={(event) => setWeekStart(event.target.value)}
          />
          {createMutation.error ? (
            <ErrorState error={createMutation.error} title="Create failed" />
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!user || createMutation.isPending}
            onClick={() => {
              if (!user) return;
              createMutation.mutate({
                user_id: user.id,
                week_start: weekStart,
              });
            }}
          >
            {createMutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(rejectTarget)}
        onClose={() => setRejectTarget(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Reject Timesheet</DialogTitle>
        <DialogContent>
          <TextField
            label="Approval Comments"
            fullWidth
            multiline
            rows={3}
            margin="normal"
            required
            value={rejectComments}
            onChange={(event) => setRejectComments(event.target.value)}
            helperText="Explain what needs to change before resubmission."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectTarget(null)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            disabled={!rejectComments.trim() || workflowMutation.isPending}
            onClick={() => {
              if (!rejectTarget) return;
              workflowMutation.mutate({
                action: 'reject',
                timesheetId: rejectTarget.id,
                comments: rejectComments,
              });
            }}
          >
            Reject
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
