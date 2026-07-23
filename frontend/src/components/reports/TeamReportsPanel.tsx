import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Paper,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
} from '@mui/material';
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import {
  getHoursByTeamReport,
  getQuotedVsActualByTeamReport,
  getTeamUtilizationReport,
  reportQueryKeys,
  type ReportOptions,
} from '../../services/reportService';
import type {
  HoursByTeamReportRow,
  QuotedVsActualByTeamReportRow,
  TeamUtilizationReportRow,
} from '../../types/Reports';
import { formatDisplayValue, formatNumber } from '../../utils/format';
import { ensureArray } from '../../types/pagination';
import { useGeneratedReportQuery } from '../../hooks/useGeneratedReportQuery';

const TEAM_TABS = [
  { label: 'Quoted vs Actual', key: 'quoted-vs-actual' },
  { label: 'Utilization', key: 'utilization' },
  { label: 'Hours', key: 'hours' },
] as const;

interface TeamReportsPanelProps {
  reportOptions: ReportOptions;
}

export function TeamReportsPanel({ reportOptions }: TeamReportsPanelProps) {
  const [teamTab, setTeamTab] = useState(0);

  const quotedQuery = useGeneratedReportQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'quoted-vs-actual'],
    queryFn: () => getQuotedVsActualByTeamReport(reportOptions),
    ready: teamTab === 0,
  });
  const utilizationQuery = useGeneratedReportQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'utilization'],
    queryFn: getTeamUtilizationReport,
    ready: teamTab === 1,
  });
  const hoursQuery = useGeneratedReportQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'hours'],
    queryFn: () => getHoursByTeamReport(reportOptions),
    ready: teamTab === 2,
  });

  const activeQuery = [quotedQuery, utilizationQuery, hoursQuery][teamTab];
  const quotedRows = ensureArray<QuotedVsActualByTeamReportRow>(
    quotedQuery.hasGenerated ? quotedQuery.data : undefined,
  );
  const utilizationRows = ensureArray<TeamUtilizationReportRow>(
    utilizationQuery.hasGenerated ? utilizationQuery.data : undefined,
  );
  const hoursRows = ensureArray<HoursByTeamReportRow>(
    hoursQuery.hasGenerated ? hoursQuery.data : undefined,
  );

  return (
    <Box>
      <Tabs
        value={teamTab}
        onChange={(_, value: number) => setTeamTab(value)}
        sx={{ mb: 2 }}
        variant="scrollable"
        scrollButtons="auto"
      >
        {TEAM_TABS.map((tab) => (
          <Tab key={tab.key} label={tab.label} />
        ))}
      </Tabs>

      <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'center' }}>
        <Button
          variant="contained"
          startIcon={<PlayArrowRoundedIcon />}
          onClick={() => activeQuery.generate()}
          disabled={activeQuery.isFetching}
        >
          {activeQuery.isFetching ? 'Generating…' : 'Generate'}
        </Button>
      </Box>

      {!activeQuery.generationRequested ? (
        <Alert severity="info" sx={{ mb: 2 }}>
          Click Generate to load this team report for the current filters.
        </Alert>
      ) : null}

      {activeQuery.generationRequested && activeQuery.isLoading ? (
        <LoadingState message="Loading team report…" />
      ) : null}
      {activeQuery.error ? <ErrorState error={activeQuery.error} /> : null}

      {teamTab === 0 && quotedQuery.hasGenerated ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Team</TableCell>
                <TableCell align="right">Quoted</TableCell>
                <TableCell align="right">Actual</TableCell>
                <TableCell align="right">Variance</TableCell>
                <TableCell align="right">Variance %</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {quotedRows.map((row) => (
                <TableRow key={row.team_id} hover>
                  <TableCell>{formatDisplayValue(row.team_name)}</TableCell>
                  <TableCell align="right">{formatNumber(row.quoted_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.variance_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.variance_percent)}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {teamTab === 1 && utilizationQuery.hasGenerated ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Team</TableCell>
                <TableCell align="right">Members</TableCell>
                <TableCell align="right">Allocated</TableCell>
                <TableCell align="right">Actual</TableCell>
                <TableCell align="right">Utilization</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {utilizationRows.map((row) => (
                <TableRow key={row.team_id ?? row.team_name} hover>
                  <TableCell>{formatDisplayValue(row.team_name)}</TableCell>
                  <TableCell align="right">{row.member_count}</TableCell>
                  <TableCell align="right">{formatNumber(row.allocated_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.utilization_percent)}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {teamTab === 2 && hoursQuery.hasGenerated ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Team</TableCell>
                <TableCell align="right">Quoted</TableCell>
                <TableCell align="right">Actual</TableCell>
                <TableCell align="right">Variance</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {hoursRows.map((row) => (
                <TableRow key={row.team_id} hover>
                  <TableCell>{formatDisplayValue(row.team_name)}</TableCell>
                  <TableCell align="right">{formatNumber(row.quoted_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.hours_variance)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}
    </Box>
  );
}
