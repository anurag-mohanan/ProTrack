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
  getCustomerByTeamReport,
  getDesignerByTeamReport,
  getHoursByTeamReport,
  getMonthlyTeamSummaryReport,
  getProjectsByTeamReport,
  getQuotedVsActualByTeamReport,
  getTeamProfitabilityReport,
  getTeamUtilizationReport,
  reportQueryKeys,
  type ReportOptions,
} from '../../services/reportService';
import { formatCellValue, formatNumber } from '../../utils/format';

const TEAM_TABS = [
  { label: 'Quoted vs Actual', key: 'quoted-vs-actual' },
  { label: 'Utilization', key: 'utilization' },
  { label: 'Projects', key: 'projects' },
  { label: 'Hours', key: 'hours' },
  { label: 'Customers', key: 'customers' },
  { label: 'Designers', key: 'designers' },
  { label: 'Profitability', key: 'profitability' },
  { label: 'Monthly Summary', key: 'monthly' },
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
  const projectsQuery = useQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'projects'],
    queryFn: () => getProjectsByTeamReport(reportOptions),
    enabled: teamTab === 2,
  });
  const hoursQuery = useQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'hours'],
    queryFn: () => getHoursByTeamReport(reportOptions),
    enabled: teamTab === 3,
  });
  const customersQuery = useQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'customers'],
    queryFn: () => getCustomerByTeamReport(reportOptions),
    enabled: teamTab === 4,
  });
  const designersQuery = useQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'designers'],
    queryFn: getDesignerByTeamReport,
    enabled: teamTab === 5,
  });
  const profitabilityQuery = useQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'profitability'],
    queryFn: () => getTeamProfitabilityReport(reportOptions),
    enabled: teamTab === 6,
  });
  const monthlyQuery = useQuery({
    queryKey: [...reportQueryKeys.teamReports(reportOptions), 'monthly'],
    queryFn: getMonthlyTeamSummaryReport,
    enabled: teamTab === 7,
  });

  const activeQuery = [
    quotedQuery,
    utilizationQuery,
    projectsQuery,
    hoursQuery,
    customersQuery,
    designersQuery,
    profitabilityQuery,
    monthlyQuery,
  ][teamTab];

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
              {(quotedQuery.data ?? []).map((row) => (
                <TableRow key={row.team_id} hover>
                  <TableCell>{row.team_name}</TableCell>
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
              {(utilizationQuery.data ?? []).map((row) => (
                <TableRow key={row.team_id ?? row.team_name} hover>
                  <TableCell>{row.team_name}</TableCell>
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

      {teamTab === 2 && !projectsQuery.isLoading && !projectsQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Team</TableCell>
                <TableCell align="right">Projects</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(projectsQuery.data ?? []).map((row) => (
                <TableRow key={row.team_id} hover>
                  <TableCell>{row.team_name}</TableCell>
                  <TableCell align="right">{row.project_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {teamTab === 3 && !hoursQuery.isLoading && !hoursQuery.error ? (
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
              {(hoursQuery.data ?? []).map((row) => (
                <TableRow key={row.team_id} hover>
                  <TableCell>{row.team_name}</TableCell>
                  <TableCell align="right">{formatNumber(row.quoted_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.hours_variance)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {teamTab === 4 && !customersQuery.isLoading && !customersQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Team</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell align="right">Projects</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(customersQuery.data ?? []).map((row) => (
                <TableRow key={`${row.team_id}-${row.customer_id}`} hover>
                  <TableCell>{row.team_name}</TableCell>
                  <TableCell>{row.customer_name}</TableCell>
                  <TableCell align="right">{row.project_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {teamTab === 5 && !designersQuery.isLoading && !designersQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Team</TableCell>
                <TableCell>Designer</TableCell>
                <TableCell>Role</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(designersQuery.data ?? []).map((row) => (
                <TableRow key={`${row.team_id}-${row.user_id}`} hover>
                  <TableCell>{row.team_name}</TableCell>
                  <TableCell>{row.user_name}</TableCell>
                  <TableCell>{formatCellValue(row.role_within_team)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {teamTab === 6 && !profitabilityQuery.isLoading && !profitabilityQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Team</TableCell>
                <TableCell align="right">Quoted</TableCell>
                <TableCell align="right">Actual</TableCell>
                <TableCell align="right">Margin</TableCell>
                <TableCell align="right">Margin %</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(profitabilityQuery.data ?? []).map((row) => (
                <TableRow key={row.team_id} hover>
                  <TableCell>{row.team_name}</TableCell>
                  <TableCell align="right">{formatNumber(row.quoted_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.margin_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.margin_percent)}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {teamTab === 7 && !monthlyQuery.isLoading && !monthlyQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Team</TableCell>
                <TableCell>Period</TableCell>
                <TableCell align="right">Actual Hours</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(monthlyQuery.data ?? []).map((row) => (
                <TableRow key={`${row.team_id}-${row.year}-${row.month}`} hover>
                  <TableCell>{row.team_name}</TableCell>
                  <TableCell>
                    {row.year}-{String(row.month).padStart(2, '0')}
                  </TableCell>
                  <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}
    </Box>
  );
}
