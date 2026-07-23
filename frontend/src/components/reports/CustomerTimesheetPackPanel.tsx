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
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded';
import { useQuery } from '@tanstack/react-query';
import { fetchCustomers, fetchTeams } from '../../api/lookups';
import {
  customerTimesheetPackQueryKeys,
  downloadCustomerTimesheetPackExcel,
  fetchCustomerTimesheetPackPreview,
} from '../../api/customerTimesheetPack';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import type {
  CustomerTimesheetAssociateRow,
  CustomerTimesheetToolRow,
} from '../../types/CustomerTimesheetPack';
import type { Customer } from '../../types';
import type { Team } from '../../types/Team';
import { formatNumber } from '../../utils/format';
import { ensureArray } from '../../types/pagination';
import { defaultAnchorForPeriod } from '../../utils/reportPeriodSelection';
import { useGeneratedReportQuery } from '../../hooks/useGeneratedReportQuery';
import {
  ReportPeriodSelectors,
  syncAnchorForPeriodChange,
} from './ReportPeriodSelectors';

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
  const [anchor, setAnchor] = useState(defaultAnchorForPeriod('weekly'));
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

  const teams = ensureArray<Team>(teamsQuery.data);
  const customers = ensureArray<Customer>(customersQuery.data);
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

  const previewQuery = useGeneratedReportQuery({
    queryKey: customerTimesheetPackQueryKeys.preview(options),
    queryFn: () => fetchCustomerTimesheetPackPreview(options),
    ready: Boolean(customerId),
  });

  const handlePeriodTypeChange = (next: 'weekly' | 'monthly') => {
    setPeriodType(next);
    setAnchor((current) => syncAnchorForPeriodChange(next, current));
  };

  const handleDownload = async () => {
    if (!canExport || !customerId || !previewQuery.canDownload) return;
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

  const payload = previewQuery.hasGenerated ? previewQuery.data : undefined;

  const controls = (
    <Stack spacing={1.5}>
      <Box
        sx={{
          display: 'grid',
          gap: 1.5,
          width: '100%',
          minWidth: 0,
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(2, minmax(0, 1fr))',
            md: 'repeat(3, minmax(0, 1fr))',
          },
          '& > *': { minWidth: 0, width: '100%' },
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
          fullWidth
          slotProps={{ inputLabel: { shrink: true } }}
        >
          <MenuItem value="">Select customer</MenuItem>
          {customers.map((customer) => (
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
          fullWidth
        >
          <MenuItem value="weekly">Weekly</MenuItem>
          <MenuItem value="monthly">Monthly</MenuItem>
        </TextField>
        <ReportPeriodSelectors
          periodType={periodType}
          anchor={anchor}
          onAnchorChange={setAnchor}
          fluid
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
          fullWidth
          slotProps={{ inputLabel: { shrink: true } }}
        >
          <MenuItem value="">All accessible teams</MenuItem>
          {teams.map((team) => (
            <MenuItem key={team.id} value={team.id}>
              {team.name}
            </MenuItem>
          ))}
        </TextField>
      </Box>
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
        <Button
          variant="contained"
          startIcon={<PlayArrowRoundedIcon />}
          disabled={!customerId || previewQuery.isFetching}
          onClick={() => previewQuery.generate()}
        >
          {previewQuery.isFetching ? 'Generating…' : 'Generate'}
        </Button>
        <Button
          variant="outlined"
          startIcon={<DownloadRoundedIcon />}
          disabled={!canExport || !previewQuery.canDownload || downloading}
          onClick={() => void handleDownload()}
        >
          {downloading ? 'Downloading…' : 'Download Excel'}
        </Button>
      </Stack>
    </Stack>
  );

  return (
    <Stack spacing={2.5}>
      {embedded ? (
        <Paper sx={{ p: 2 }}>
          <Stack spacing={1.5}>
            <Typography variant="body2" color="text.secondary">
              Select customer, period (week or month), and team if you lead more than one. Click
              Generate to preview. Totals include draft, submitted, and approved hours.
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
              Prosohm-style weekly or monthly timesheet for one customer. Click Generate to preview,
              then Download Excel. Includes draft, submitted, and approved hours — productive vs NP,
              utilization, and tool rollup.
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
        <Alert severity="info">Select a customer, then click Generate to build the timesheet pack.</Alert>
      ) : !previewQuery.generationRequested ? (
        <Alert severity="info">Click Generate to preview this customer timesheet pack.</Alert>
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
                {ensureArray<CustomerTimesheetAssociateRow>(payload.associates).map((row) => (
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
                {!ensureArray<CustomerTimesheetAssociateRow>(payload.associates).length ? (
                  <TableRow>
                    <TableCell colSpan={8}>
                      <Typography variant="body2" color="text.secondary">
                        No timesheet hours found for this customer in the selected period
                        {teamId ? ' and team' : ''}. Check that hours are booked on this customer&apos;s
                        projects, the period dates are correct, and (if used) the team filter matches
                        the people or projects that logged the work.
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
                {ensureArray<CustomerTimesheetToolRow>(payload.tools).map((row) => (
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
                      ensureArray<CustomerTimesheetToolRow>(payload.tools).reduce(
                        (sum, row) => sum + Number(row.hours || 0),
                        0,
                      ),
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
