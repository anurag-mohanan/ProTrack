import { useState } from 'react';
import {
  Box,
  FormControlLabel,
  Paper,
  Switch,
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
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { ContentCard } from '../components/ui/cards';
import { StatusChip } from '../components/common/StatusChip';
import { useAuth } from '../context/AuthContext';
import {
  getBillableUtilizationReport,
  getCustomerSummaryReport,
  getDesignerUtilizationReport,
  getMonthlyNpTrendsReport,
  getNonProductiveHoursReport,
  getProductiveHoursReport,
  getProjectHoursReport,
  reportQueryKeys,
  type ReportOptions,
} from '../services/reportService';
import type { ProjectStatus } from '../types';
import { canViewDeletedProjects } from '../utils/permissions';
import { formatNumber } from '../utils/format';

const TAB_LABELS = [
  'Project Hours',
  'Productive Hours',
  'Non-Productive Hours',
  'Billable Utilization',
  'Monthly NP Trends',
  'Designer Utilization',
  'Customer Summary',
] as const;

export function ReportsPage() {
  const [tab, setTab] = useState(0);
  const { user } = useAuth();
  const [includeArchived, setIncludeArchived] = useState(true);
  const [includeDeleted, setIncludeDeleted] = useState(false);

  const reportOptions: ReportOptions = {
    include_archived: includeArchived,
    include_deleted: includeDeleted,
  };

  const projectHoursQuery = useQuery({
    queryKey: reportQueryKeys.projectHours(reportOptions),
    queryFn: () => getProjectHoursReport(reportOptions),
    enabled: tab === 0,
  });

  const productiveQuery = useQuery({
    queryKey: reportQueryKeys.productiveHours,
    queryFn: getProductiveHoursReport,
    enabled: tab === 1,
  });

  const npHoursQuery = useQuery({
    queryKey: reportQueryKeys.nonProductiveHours,
    queryFn: getNonProductiveHoursReport,
    enabled: tab === 2,
  });

  const billableQuery = useQuery({
    queryKey: reportQueryKeys.billableUtilization,
    queryFn: getBillableUtilizationReport,
    enabled: tab === 3,
  });

  const npTrendsQuery = useQuery({
    queryKey: reportQueryKeys.monthlyNpTrends,
    queryFn: getMonthlyNpTrendsReport,
    enabled: tab === 4,
  });

  const designerQuery = useQuery({
    queryKey: reportQueryKeys.designerUtilization,
    queryFn: getDesignerUtilizationReport,
    enabled: tab === 5,
  });

  const customerQuery = useQuery({
    queryKey: reportQueryKeys.customerSummary(reportOptions),
    queryFn: () => getCustomerSummaryReport(reportOptions),
    enabled: tab === 6,
  });

  const activeQuery =
    tab === 0
      ? projectHoursQuery
      : tab === 1
        ? productiveQuery
        : tab === 2
          ? npHoursQuery
          : tab === 3
            ? billableQuery
            : tab === 4
              ? npTrendsQuery
              : tab === 5
                ? designerQuery
                : customerQuery;

  return (
    <Box>
      <PageHeader
        title="Reports"
        subtitle="Productive and non-productive hours, utilization, and portfolio summaries"
      />

      <Box sx={{ mb: 3 }}>
        <ContentCard>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <FormControlLabel
              control={
                <Switch
                  checked={includeArchived}
                  onChange={(event) => setIncludeArchived(event.target.checked)}
                />
              }
              label="Include Archived"
            />
            {canViewDeletedProjects(user?.role_name ?? '') ? (
              <FormControlLabel
                control={
                  <Switch
                    checked={includeDeleted}
                    onChange={(event) => setIncludeDeleted(event.target.checked)}
                  />
                }
                label="Include Deleted (Admin)"
              />
            ) : null}
          </Box>
        </ContentCard>
      </Box>

      <Tabs
        value={tab}
        onChange={(_, value) => setTab(value)}
        sx={{ mb: 3 }}
        variant="scrollable"
        scrollButtons="auto"
      >
        {TAB_LABELS.map((label) => (
          <Tab key={label} label={label} />
        ))}
      </Tabs>

      {activeQuery.isLoading ? <LoadingState message="Loading reports…" /> : null}
      {activeQuery.error ? <ErrorState error={activeQuery.error} /> : null}

      {tab === 0 && !projectHoursQuery.isLoading && !projectHoursQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Tool Number</TableCell>
                <TableCell>Description</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell align="right">Quoted</TableCell>
                <TableCell align="right">Actual</TableCell>
                <TableCell align="right">Variance</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(projectHoursQuery.data ?? []).map((row) => (
                <TableRow key={row.project_id} hover>
                  <TableCell>{row.tool_number}</TableCell>
                  <TableCell>{row.part_description}</TableCell>
                  <TableCell>{row.customer_name}</TableCell>
                  <TableCell align="right">{formatNumber(row.quoted_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.hours_variance)}</TableCell>
                  <TableCell>
                    <StatusChip status={row.status as ProjectStatus} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {tab === 1 && !productiveQuery.isLoading && !productiveQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Project</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell>Task</TableCell>
                <TableCell align="right">Total</TableCell>
                <TableCell align="right">Billable</TableCell>
                <TableCell align="right">Non-Billable</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(productiveQuery.data ?? []).map((row, index) => (
                <TableRow key={`${row.project_id ?? 'none'}-${row.task_type_name}-${index}`} hover>
                  <TableCell>{row.tool_number ?? '—'}</TableCell>
                  <TableCell>{row.customer_name ?? '—'}</TableCell>
                  <TableCell>{row.task_type_name ?? '—'}</TableCell>
                  <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.billable_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.non_billable_hours)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {tab === 2 && !npHoursQuery.isLoading && !npHoursQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>NP Code</TableCell>
                <TableCell>Description</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell align="right">Hours</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(npHoursQuery.data ?? []).map((row) => (
                <TableRow key={row.non_productive_code} hover>
                  <TableCell>{row.non_productive_code}</TableCell>
                  <TableCell>{row.description}</TableCell>
                  <TableCell>{row.customer_name ?? '—'}</TableCell>
                  <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {tab === 3 && !billableQuery.isLoading && !billableQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Designer</TableCell>
                <TableCell align="right">Billable</TableCell>
                <TableCell align="right">Non-Billable</TableCell>
                <TableCell align="right">NP Hours</TableCell>
                <TableCell align="right">Billable %</TableCell>
                <TableCell align="right">Non-Billable %</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(billableQuery.data ?? []).map((row) => (
                <TableRow key={row.user_id} hover>
                  <TableCell>{row.designer_name}</TableCell>
                  <TableCell align="right">{formatNumber(row.billable_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.non_billable_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.np_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.billable_percent)}%</TableCell>
                  <TableCell align="right">{formatNumber(row.non_billable_percent)}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {tab === 4 && !npTrendsQuery.isLoading && !npTrendsQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Month</TableCell>
                <TableCell align="right">NP Hours</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(npTrendsQuery.data ?? []).map((row) => (
                <TableRow key={row.month} hover>
                  <TableCell>{row.month}</TableCell>
                  <TableCell align="right">{formatNumber(row.total_np_hours)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {tab === 5 && !designerQuery.isLoading && !designerQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Designer</TableCell>
                <TableCell>Role</TableCell>
                <TableCell align="right">Active Projects</TableCell>
                <TableCell align="right">Hours This Week</TableCell>
                <TableCell align="right">Quoted Assigned</TableCell>
                <TableCell align="right">Actual Logged</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(designerQuery.data ?? []).map((row) => (
                <TableRow key={row.user_id} hover>
                  <TableCell>{row.designer_name}</TableCell>
                  <TableCell>{row.role}</TableCell>
                  <TableCell align="right">{row.active_projects}</TableCell>
                  <TableCell align="right">{formatNumber(row.hours_this_week)}</TableCell>
                  <TableCell align="right">{formatNumber(row.quoted_hours_assigned)}</TableCell>
                  <TableCell align="right">{formatNumber(row.actual_hours_logged)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {tab === 6 && !customerQuery.isLoading && !customerQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Customer</TableCell>
                <TableCell align="right">Projects</TableCell>
                <TableCell align="right">Quoted Hours</TableCell>
                <TableCell align="right">Actual Hours</TableCell>
                <TableCell align="right">Variance</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(customerQuery.data ?? []).map((row) => (
                <TableRow key={row.customer_id} hover>
                  <TableCell>{row.customer_name}</TableCell>
                  <TableCell align="right">{row.project_count}</TableCell>
                  <TableCell align="right">{formatNumber(row.total_quoted_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(row.total_actual_hours)}</TableCell>
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
