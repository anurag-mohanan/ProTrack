import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded';
import { useQuery } from '@tanstack/react-query';
import { fetchCustomers, fetchTeams } from '../../api/lookups';
import {
  customerTimesheetPackQueryKeys,
  downloadCustomerTimesheetPackExcel,
  fetchCustomerTimesheetPackPreview,
} from '../../api/customerTimesheetPack';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { formatNumber } from '../../utils/format';
import { ensureArray } from '../../types/pagination';

function toIsoDate(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
}

function mondayOfWeek(value = new Date()): string {
  const day = value.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  const monday = new Date(value);
  monday.setDate(value.getDate() + diff);
  return toIsoDate(monday);
}

function firstOfMonth(value = new Date()): string {
  return toIsoDate(new Date(value.getFullYear(), value.getMonth(), 1));
}

function weekRangeLabel(anchor: string): string {
  const start = new Date(`${anchor}T00:00:00`);
  if (Number.isNaN(start.getTime())) return '';
  const end = new Date(start);
  end.setDate(start.getDate() + 4);
  const fmt = (d: Date) =>
    d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
  return `${fmt(start)} – ${fmt(end)} (Mon–Fri)`;
}

function monthLabel(anchor: string): string {
  const start = new Date(`${anchor}T00:00:00`);
  if (Number.isNaN(start.getTime())) return '';
  return start.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

interface CustomerTimesheetPackPanelProps {
  canExport: boolean;
  /** When embedded in Engineering Suite, hide the outer title card. */
  embedded?: boolean;
}

export function CustomerTimesheetPackPanel({
  canExport,
  embedded = false,
}: CustomerTimesheetPackPanelProps) {
  const [customerId, setCustomerId] = useState('');
  const [teamId, setTeamId] = useState('');
  const [periodType, setPeriodType] = useState<'weekly' | 'monthly'>('weekly');
  const [anchor, setAnchor] = useState(mondayOfWeek());
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const customersQuery = useQuery({
    queryKey: ['lookups', 'customers'],
    queryFn: fetchCustomers,
    staleTime: 5 * 60 * 1000,
  });
  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams'],
    queryFn: fetchTeams,
    staleTime: 5 * 60 * 1000,
  });

  const teams = ensureArray(teamsQuery.data);
  const customers = ensureArray(customersQuery.data);
  const multiTeam = teams.length > 1;

  const options = useMemo(
    () => ({
      customer_id: customerId,
      period_type: periodType,
      anchor,
      team_id: teamId || undefined,
    }),
    [customerId, periodType, anchor, teamId],
  );

  const previewQuery = useQuery({
    queryKey: customerTimesheetPackQueryKeys.preview(options),
    queryFn: () => fetchCustomerTimesheetPackPreview(options),
    enabled: Boolean(customerId),
    staleTime: 60 * 1000,
  });

  const handlePeriodTypeChange = (next: 'weekly' | 'monthly') => {
    setPeriodType(next);
    setAnchor(next === 'weekly' ? mondayOfWeek() : firstOfMonth());
  };

  const handleDownload = async () => {
    if (!canExport || !customerId) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadCustomerTimesheetPackExcel(options);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Download failed');
    } finally {
      setDownloading(false);
    }
  };

  const payload = previewQuery.data;
  const periodHelper =
    periodType === 'weekly' ? weekRangeLabel(anchor) : monthLabel(anchor);

  const controls = (
    <Box
      sx={{
        display: 'grid',
        gap: 1.5,
        gridTemplateColumns: { xs: '1fr', md: '1.5fr 1fr 1.2fr 1.2fr auto' },
        alignItems: 'start',
      }}
    >
      <TextField
        select
        size="small"
        label="Customer"
        required
        value={customerId}
        onChange={(event) => setCustomerId(event.target.value)}
        helperText="Required — pack is always for one customer"
      >
        <MenuItem value="">Select customer</MenuItem>
        {(customers).map((customer) => (
          <MenuItem key={customer.id} value={customer.id}>
            {customer.name}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        select
        size="small"
        label="Week or month"
        value={periodType}
        onChange={(event) => handlePeriodTypeChange(event.target.value as 'weekly' | 'monthly')}
      >
        <MenuItem value="weekly">Weekly</MenuItem>
        <MenuItem value="monthly">Monthly</MenuItem>
      </TextField>
      <TextField
        size="small"
        type="date"
        label={periodType === 'weekly' ? 'Week (any day)' : 'Month (any day)'}
        value={anchor}
        onChange={(event) => setAnchor(event.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
        helperText={periodHelper || 'Pick a date in the period'}
      />
      <TextField
        select
        size="small"
        label="Team"
        value={teamId}
        onChange={(event) => setTeamId(event.target.value)}
        helperText={
          multiTeam
            ? 'Leaders with multiple teams: pick one, or leave as all accessible'
            : 'Optional team filter'
        }
      >
        <MenuItem value="">All accessible teams</MenuItem>
        {teams.map((team) => (
          <MenuItem key={team.id} value={team.id}>
            {team.name}
          </MenuItem>
        ))}
      </TextField>
      <Button
        variant="contained"
        startIcon={<DownloadRoundedIcon />}
        disabled={!canExport || !customerId || downloading || previewQuery.isFetching}
        onClick={() => void handleDownload()}
        sx={{ mt: 0.5 }}
      >
        {downloading ? 'Downloading…' : 'Download Excel'}
      </Button>
    </Box>
  );

  return (
    <Stack spacing={2.5}>
      {embedded ? (
        <Paper sx={{ p: 2 }}>
          <Stack spacing={1.5}>
            <Typography variant="body2" color="text.secondary">
              Select customer, period (week or month), and team if you lead more than one. Only
              submitted/approved hours are included.
            </Typography>
            {controls}
            {!canExport ? (
              <Alert severity="info">Preview is available; export requires export permission.</Alert>
            ) : null}
            {downloadError ? <Alert severity="error">{downloadError}</Alert> : null}
          </Stack>
        </Paper>
      ) : (
        <Paper sx={{ p: 2.5 }}>
          <Stack spacing={1.5}>
            <Typography variant="h6">Customer Timesheet Pack</Typography>
            <Typography variant="body2" color="text.secondary">
              Prosohm-style weekly or monthly timesheet for subscription / fixed-resource customers.
              Includes associate productive vs NP hours, utilization, and tool rollup for customer AP.
            </Typography>
            {controls}
            {!canExport ? (
              <Alert severity="info">
                You can preview this pack, but export requires export permission.
              </Alert>
            ) : null}
            {downloadError ? <Alert severity="error">{downloadError}</Alert> : null}
          </Stack>
        </Paper>
      )}

      {!customerId ? (
        <Alert severity="info">Select a customer to preview the timesheet pack.</Alert>
      ) : previewQuery.isLoading ? (
        <LoadingState message="Building customer timesheet pack…" />
      ) : previewQuery.error ? (
        <ErrorState error={previewQuery.error} title="Unable to load timesheet pack" />
      ) : payload ? (
        <Stack spacing={2}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {payload.title} — {payload.customer_name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {payload.period.label}
              {payload.week_number != null ? ` · Week of ${payload.week_number}` : ''} · Working Hrs.{' '}
              {formatNumber(payload.working_hours_target)}
            </Typography>
          </Paper>

          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Sl</TableCell>
                  <TableCell>Associate</TableCell>
                  <TableCell>Designation</TableCell>
                  <TableCell align="right">Productive</TableCell>
                  <TableCell align="right">Non-productive</TableCell>
                  <TableCell align="right">TOTAL</TableCell>
                  <TableCell align="right" sx={{ bgcolor: 'warning.light' }}>
                    Utilization
                  </TableCell>
                  <TableCell>Remarks</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {payload.associates.map((row) => (
                  <TableRow key={row.user_id} hover>
                    <TableCell>{row.serial_no}</TableCell>
                    <TableCell>{row.associate_name}</TableCell>
                    <TableCell>{row.designation ?? '—'}</TableCell>
                    <TableCell align="right">{formatNumber(row.productive_hours)}</TableCell>
                    <TableCell align="right">{formatNumber(row.non_productive_hours)}</TableCell>
                    <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                    <TableCell align="right">{formatNumber(row.utilization_percent)}%</TableCell>
                    <TableCell>{row.remarks ?? '—'}</TableCell>
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell colSpan={3} sx={{ fontWeight: 700 }}>
                    TOTAL
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {formatNumber(payload.total_productive_hours)}
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {formatNumber(payload.total_non_productive_hours)}
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {formatNumber(payload.total_hours)}
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {formatNumber(payload.overall_utilization_percent)}%
                  </TableCell>
                  <TableCell />
                </TableRow>
                {!payload.associates.length ? (
                  <TableRow>
                    <TableCell colSpan={8}>
                      <Typography variant="body2" color="text.secondary">
                        No submitted/approved hours for this customer in the selected period
                        {teamId ? ' and team' : ''}.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </TableContainer>

          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>TOOL No.</TableCell>
                  <TableCell align="right">Sum of HOURS</TableCell>
                  <TableCell>Comments</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {payload.tools.map((row) => (
                  <TableRow key={row.tool_number} hover>
                    <TableCell>{row.tool_number}</TableCell>
                    <TableCell align="right">{formatNumber(row.hours)}</TableCell>
                    <TableCell>{row.comments ?? '—'}</TableCell>
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Total</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {formatNumber(
                      payload.tools.reduce((sum, row) => sum + Number(row.hours || 0), 0),
                    )}
                  </TableCell>
                  <TableCell />
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Stack>
      ) : null}
    </Stack>
  );
}
