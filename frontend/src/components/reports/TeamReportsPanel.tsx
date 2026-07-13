import { useState } from 'react';
import {
  Box,
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
import { useQuery } from '@tanstack/react-query';
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

  const quotedQuery = useQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'quoted-vs-actual'],
    queryFn: () => getQuotedVsActualByTeamReport(reportOptions),
    enabled: teamTab === 0,
  });
  const utilizationQuery = useQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'utilization'],
    queryFn: getTeamUtilizationReport,
    enabled: teamTab === 1,
  });
  const hoursQuery = useQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'hours'],
    queryFn: () => getHoursByTeamReport(reportOptions),
    enabled: teamTab === 2,
  });

  const activeQuery = [quotedQuery, utilizationQuery, hoursQuery][teamTab];
  const quotedRows = ensureArray<QuotedVsActualByTeamReportRow>(quotedQuery.data);
  const utilizationRows = ensureArray<TeamUtilizationReportRow>(utilizationQuery.data);
  const hoursRows = ensureArray<HoursByTeamReportRow>(hoursQuery.data);

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

      {activeQuery.isLoading ? <LoadingState message="Loading team report…" /> : null}
      {activeQuery.error ? <ErrorState error={activeQuery.error} /> : null}

      {teamTab === 0 && !quotedQuery.isLoading && !quotedQuery.error ? (
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

      {teamTab === 1 && !utilizationQuery.isLoading && !utilizationQuery.error ? (
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

      {teamTab === 2 && !hoursQuery.isLoading && !hoursQuery.error ? (
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
