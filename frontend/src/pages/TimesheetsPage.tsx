import { Fragment, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { createTimesheet, fetchTimesheetEntries, fetchTimesheets } from '../api/timesheets';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { useAuth } from '../context/AuthContext';
import { formatDate, formatNumber, formatStatus } from '../utils/format';

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

  const timesheetsQuery = useQuery({
    queryKey: ['timesheets'],
    queryFn: () => fetchTimesheets(),
  });

  const entriesQuery = useQuery({
    queryKey: ['timesheet-entries', expandedId],
    queryFn: () => fetchTimesheetEntries({ timesheet_id: expandedId ?? undefined }),
    enabled: Boolean(expandedId),
  });

  const createMutation = useMutation({
    mutationFn: createTimesheet,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['timesheets'] });
      setCreateOpen(false);
      setWeekStart(weekStartMonday());
    },
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

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3, gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }} gutterBottom>
            Timesheets
          </Typography>
          <Typography color="text.secondary">
            Weekly timesheets and logged hours
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setCreateOpen(true)}
          disabled={!user}
        >
          Create Timesheet
        </Button>
      </Box>

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
                return (
                  <Fragment key={timesheet.id}>
                    <TableRow hover>
                      <TableCell>{formatDate(timesheet.week_start)}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={formatStatus(timesheet.status)}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          onClick={() =>
                            setExpandedId(isExpanded ? null : timesheet.id)
                          }
                        >
                          {isExpanded ? 'Hide Entries' : 'View Entries'}
                        </Button>
                        <Button
                          size="small"
                          component={Link}
                          to={`/timesheets/${timesheet.id}/entries/new`}
                        >
                          Add Entry
                        </Button>
                      </TableCell>
                    </TableRow>
                    {isExpanded ? (
                      <TableRow key={`${timesheet.id}-entries`}>
                        <TableCell colSpan={3} sx={{ bgcolor: 'grey.50' }}>
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
                                  <TableCell align="right">Hours</TableCell>
                                  <TableCell>Description</TableCell>
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {entriesQuery.data.map((entry) => (
                                  <TableRow key={entry.id}>
                                    <TableCell>{formatDate(entry.entry_date)}</TableCell>
                                    <TableCell align="right">
                                      {formatNumber(entry.hours)}
                                    </TableCell>
                                    <TableCell>{entry.description ?? '—'}</TableCell>
                                  </TableRow>
                                ))}
                                <TableRow>
                                  <TableCell>
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
                status: 'draft',
              });
            }}
          >
            {createMutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
