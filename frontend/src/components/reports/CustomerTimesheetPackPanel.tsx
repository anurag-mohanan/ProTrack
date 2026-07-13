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

function mondayOfCurrentWeek(): string {
  const now = new Date();
  const day = now.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  const monday = new Date(now);
  monday.setDate(now.getDate() + diff);
  const month = String(monday.getMonth() + 1).padStart(2, '0');
  const date = String(monday.getDate()).padStart(2, '0');
  return `${monday.getFullYear()}-${month}-${date}`;
}

interface CustomerTimesheetPackPanelProps {
  canExport: boolean;
}

export function CustomerTimesheetPackPanel({ canExport }: CustomerTimesheetPackPanelProps) {
  const [customerId, setCustomerId] = useState('');
  const [teamId, setTeamId] = useState('');
  const [periodType, setPeriodType] = useState<'weekly' | 'monthly'>('weekly');
  const [anchor, setAnchor] = useState(mondayOfCurrentWeek());
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

  return (
    <Stack spacing={2.5}>
      <Paper sx={{ p: 2.5 }}>
        <Stack spacing={1.5}>
          <Typography variant="h6">Customer Timesheet Pack</Typography>
          <Typography variant="body2" color="text.secondary">
            Generate a Prosohm-style weekly or monthly timesheet for subscription / fixed-resource
            customers. Includes associate productive vs NP hours, utilization, and tool rollup for
            customer AP booking.
          </Typography>
          <Box
            sx={{
              display: 'grid',
              gap: 1.5,
              gridTemplateColumns: { xs: '1fr', md: '1.4fr 1fr 1fr 1fr auto' },
              alignItems: 'center',
            }}
          >
            <TextField
              select
              size="small"
              label="Customer"
              required
              value={customerId}
              onChange={(event) => setCustomerId(event.target.value)}
            >
              <MenuItem value="">Select customer</MenuItem>
              {(customersQuery.data ?? []).map((customer) => (
                <MenuItem key={customer.id} value={customer.id}>
                  {customer.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label="Period"
              value={periodType}
              onChange={(event) => setPeriodType(event.target.value as 'weekly' | 'monthly')}
            >
              <MenuItem value="weekly">Weekly</MenuItem>
              <MenuItem value="monthly">Monthly</MenuItem>
            </TextField>
            <TextField
              size="small"
              type="date"
              label="Anchor date"
              value={anchor}
              onChange={(event) => setAnchor(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              helperText={periodType === 'weekly' ? 'Any day in the week' : 'Any day in the month'}
            />
            <TextField
              select
              size="small"
              label="Team (optional)"
              value={teamId}
              onChange={(event) => setTeamId(event.target.value)}
            >
              <MenuItem value="">All accessible teams</MenuItem>
              {(teamsQuery.data ?? []).map((team) => (
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
            >
              {downloading ? 'Downloading…' : 'Download Excel'}
            </Button>
          </Box>
          {!canExport ? (
            <Alert severity="info">You can preview this pack, but export requires export permission.</Alert>
          ) : null}
          {downloadError ? <Alert severity="error">{downloadError}</Alert> : null}
        </Stack>
      </Paper>

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
                        No submitted/approved hours for this customer in the selected period.
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
