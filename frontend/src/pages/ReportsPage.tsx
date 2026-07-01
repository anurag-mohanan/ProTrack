import { useEffect, useMemo, useState } from 'react';
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
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { ContentCard } from '../components/ui/cards';
import { StatusChip } from '../components/common/StatusChip';
import { useAuth } from '../context/AuthContext';
import {
  getBillableUtilizationReport,
  getBillableVsNonBillableReport,
  getCustomerSummaryReport,
  getDesignerUtilizationReport,
  getMonthlyNpTrendsReport,
  getNonProductiveHoursReport,
  getNpHoursByDesignerReport,
  getProductiveHoursReport,
  getProjectHoursReport,
  getTopNpActivitiesReport,
  reportQueryKeys,
  type ReportOptions,
} from '../services/reportService';
import type { ProjectStatus } from '../types';
import { canViewDeletedProjects } from '../utils/permissions';
import { formatNumber } from '../utils/format';

const TAB_CONFIG = [
  { label: 'Project Hours', slug: 'project-hours' },
  { label: 'Productive Hours', slug: 'productive-hours' },
  { label: 'NP Hours by Code', slug: 'np-hours' },
  { label: 'NP Hours by Designer', slug: 'np-by-designer' },
  { label: 'NP Hours by Month', slug: 'np-by-month' },
  { label: 'Billable vs Non-Billable', slug: 'billable-vs-np' },
  { label: 'Top NP Activities', slug: 'top-np' },
  { label: 'Billable Utilization', slug: 'billable-utilization' },
  { label: 'Designer Utilization', slug: 'designer-utilization' },
  { label: 'Customer Summary', slug: 'customer-summary' },
] as const;

function tabIndexFromSlug(slug: string | null): number {
  if (!slug) return 0;
  const index = TAB_CONFIG.findIndex((tab) => tab.slug === slug);
  return index >= 0 ? index : 0;
}

export function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = tabIndexFromSlug(searchParams.get('tab'));
  const [tab, setTab] = useState(initialTab);
  const { user } = useAuth();
  const [includeArchived, setIncludeArchived] = useState(true);
  const [includeDeleted, setIncludeDeleted] = useState(false);

  useEffect(() => {
    setTab(tabIndexFromSlug(searchParams.get('tab')));
  }, [searchParams]);

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

  const npByDesignerQuery = useQuery({
    queryKey: reportQueryKeys.npHoursByDesigner,
    queryFn: getNpHoursByDesignerReport,
    enabled: tab === 3,
  });

  const npTrendsQuery = useQuery({
    queryKey: reportQueryKeys.monthlyNpTrends,
    queryFn: getMonthlyNpTrendsReport,
    enabled: tab === 4,
  });

  const billableVsNpQuery = useQuery({
    queryKey: reportQueryKeys.billableVsNonBillable,
    queryFn: getBillableVsNonBillableReport,
    enabled: tab === 5,
  });

  const topNpQuery = useQuery({
    queryKey: reportQueryKeys.topNpActivities,
    queryFn: getTopNpActivitiesReport,
    enabled: tab === 6,
  });

  const billableQuery = useQuery({
    queryKey: reportQueryKeys.billableUtilization,
    queryFn: getBillableUtilizationReport,
    enabled: tab === 7,
  });

  const designerQuery = useQuery({
    queryKey: reportQueryKeys.designerUtilization,
    queryFn: getDesignerUtilizationReport,
    enabled: tab === 8,
  });

  const customerQuery = useQuery({
    queryKey: reportQueryKeys.customerSummary(reportOptions),
    queryFn: () => getCustomerSummaryReport(reportOptions),
    enabled: tab === 9,
  });

  const activeQuery = useMemo(() => {
    const queries = [
      projectHoursQuery,
      productiveQuery,
      npHoursQuery,
      npByDesignerQuery,
      npTrendsQuery,
      billableVsNpQuery,
      topNpQuery,
      billableQuery,
      designerQuery,
      customerQuery,
    ];
    return queries[tab] ?? projectHoursQuery;
  }, [
    tab,
    projectHoursQuery,
    productiveQuery,
    npHoursQuery,
    npByDesignerQuery,
    npTrendsQuery,
    billableVsNpQuery,
    topNpQuery,
    billableQuery,
    designerQuery,
    customerQuery,
  ]);

  const handleTabChange = (_: unknown, value: number) => {
    setTab(value);
    setSearchParams({ tab: TAB_CONFIG[value].slug });
  };

  return (
    <Box>
      <PageHeader
        title="Reports"
        subtitle="Business intelligence"
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
        onChange={handleTabChange}
        sx={{ mb: 3 }}
        variant="scrollable"
        scrollButtons="auto"
      >
        {TAB_CONFIG.map((config) => (
          <Tab key={config.slug} label={config.label} />
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

      {tab === 3 && !npByDesignerQuery.isLoading && !npByDesignerQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Designer</TableCell>
                <TableCell align="right">NP Hours</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(npByDesignerQuery.data ?? []).map((row) => (
                <TableRow key={row.user_id} hover>
                  <TableCell>{row.designer_name}</TableCell>
                  <TableCell align="right">{formatNumber(row.total_np_hours)}</TableCell>
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

      {tab === 5 && !billableVsNpQuery.isLoading && !billableVsNpQuery.error && billableVsNpQuery.data ? (
        <Paper sx={{ p: 3, maxWidth: 480 }}>
          <Box sx={{ display: 'grid', gap: 1.5 }}>
            <Typography variant="body2">
              Billable hours: {formatNumber(billableVsNpQuery.data.billable_hours)} (
              {formatNumber(billableVsNpQuery.data.billable_percent)}%)
            </Typography>
            <Typography variant="body2">
              Non-billable hours: {formatNumber(billableVsNpQuery.data.non_billable_hours)}
            </Typography>
            <Typography variant="body2">
              Non-productive hours: {formatNumber(billableVsNpQuery.data.np_hours)}
            </Typography>
            <Typography variant="body2">
              Combined non-billable share: {formatNumber(billableVsNpQuery.data.non_billable_percent)}%
            </Typography>
          </Box>
        </Paper>
      ) : null}

      {tab === 6 && !topNpQuery.isLoading && !topNpQuery.error ? (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>NP Code</TableCell>
                <TableCell>Description</TableCell>
                <TableCell align="right">Hours</TableCell>
                <TableCell align="right">Entries</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(topNpQuery.data ?? []).map((row) => (
                <TableRow key={row.non_productive_code} hover>
                  <TableCell>{row.non_productive_code}</TableCell>
                  <TableCell>{row.description}</TableCell>
                  <TableCell align="right">{formatNumber(row.total_hours)}</TableCell>
                  <TableCell align="right">{row.entry_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      {tab === 7 && !billableQuery.isLoading && !billableQuery.error ? (
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

      {tab === 8 && !designerQuery.isLoading && !designerQuery.error ? (
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

      {tab === 9 && !customerQuery.isLoading && !customerQuery.error ? (
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
