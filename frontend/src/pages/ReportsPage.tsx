import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  FormControlLabel,
  Stack,
  Switch,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { PageContainer } from '../components/common/PageContainer';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import {
  FilterDrawer,
  FilterGroup,
  FilterToolbar,
  FormSelect,
  ModernPageHeader,
  compactFilterFieldSx,
} from '../components/ui/design-system';
import { REPORT_CATEGORIES, type ReportCategoryId } from '../components/reports/reportCategories';
import {
  BillableUtilizationReportView,
  BillableVsNpReportView,
  CustomerSummaryReportView,
  DesignerUtilizationReportView,
  ExecutionSummaryReportView,
  NpTrendReportView,
  PortfolioReportView,
  ProjectHoursReportView,
  SimpleTableReportView,
  StageSummaryReportView,
} from '../components/reports/ReportAnalyticsViews';
import { TeamReportsPanel } from '../components/reports/TeamReportsPanel';
import { fetchCustomers, fetchTeams, fetchUsers, fetchTaskTypes } from '../api/lookups';
import { fetchProjects } from '../api/projects';
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
  getProjectPortfolioReport,
  getProjectStageSummaryReport,
  getExecutionStatusSummaryReport,
  getTopNpActivitiesReport,
  getTimesheetExportReport,
  reportQueryKeys,
  type ReportOptions,
} from '../services/reportService';
import { accessContextFromUser, canExportReports, canViewDeletedProjects } from '../utils/permissions';
import { formatNumber } from '../utils/format';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';

const TAB_CONFIG = [
  { label: 'Project Hours', slug: 'project-hours', category: 'projects' },
  { label: 'Productive Hours', slug: 'productive-hours', category: 'timesheets' },
  { label: 'NP Hours by Code', slug: 'np-hours', category: 'leave' },
  { label: 'NP Hours by Designer', slug: 'np-by-designer', category: 'leave' },
  { label: 'NP Hours by Month', slug: 'np-by-month', category: 'leave' },
  { label: 'Billable vs Non-Billable', slug: 'billable-vs-np', category: 'leave' },
  { label: 'Top NP Activities', slug: 'top-np', category: 'leave' },
  { label: 'Billable Utilization', slug: 'billable-utilization', category: 'resources' },
  { label: 'Designer Utilization', slug: 'designer-utilization', category: 'resources' },
  { label: 'Customer Summary', slug: 'customer-summary', category: 'customers' },
  { label: 'By Project Stage', slug: 'by-stage', category: 'projects' },
  { label: 'By Execution Status', slug: 'by-execution-status', category: 'projects' },
  { label: 'Project Portfolio', slug: 'project-portfolio', category: 'projects' },
  { label: 'Timesheet Export', slug: 'timesheet-export', category: 'timesheets' },
  { label: 'Team Reports', slug: 'team-reports', category: 'planning' },
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
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [appliedCategory, setAppliedCategory] = useState<ReportCategoryId | 'all'>('all');
  const [draftCategory, setDraftCategory] = useState<ReportCategoryId | 'all'>('all');
  const { user } = useAuth();
  const [appliedIncludeArchived, setAppliedIncludeArchived] = useState(true);
  const [draftIncludeArchived, setDraftIncludeArchived] = useState(true);
  const [appliedIncludeDeleted, setAppliedIncludeDeleted] = useState(false);
  const [draftIncludeDeleted, setDraftIncludeDeleted] = useState(false);
  const [exportPeriod, setExportPeriod] = useState<'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly'>('monthly');
  const [exportFilters, setExportFilters] = useState<{
    team_id: string;
    user_id: string;
    customer_id: string;
    project_id: string;
    task_type_id: string;
    billable: '' | 'billable' | 'non_billable';
  }>({ team_id: '', user_id: '', customer_id: '', project_id: '', task_type_id: '', billable: '' });

  const access = accessContextFromUser(user);
  const canExport = canExportReports(access);

  useEffect(() => {
    setTab(tabIndexFromSlug(searchParams.get('tab')));
  }, [searchParams]);

  const reportOptions: ReportOptions = {
    include_archived: appliedIncludeArchived,
    include_deleted: appliedIncludeDeleted,
  };

  const visibleTabs = useMemo(() => {
    if (appliedCategory === 'all') return TAB_CONFIG;
    const cat = REPORT_CATEGORIES.find((c) => c.id === appliedCategory);
    if (!cat) return TAB_CONFIG;
    return TAB_CONFIG.filter((t) => (cat.slugs as readonly string[]).includes(t.slug));
  }, [appliedCategory]);

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
  const stageSummaryQuery = useQuery({
    queryKey: reportQueryKeys.projectStageSummary(reportOptions),
    queryFn: () => getProjectStageSummaryReport(reportOptions),
    enabled: tab === 10,
  });
  const executionSummaryQuery = useQuery({
    queryKey: reportQueryKeys.executionStatusSummary(reportOptions),
    queryFn: () => getExecutionStatusSummaryReport(reportOptions),
    enabled: tab === 11,
  });
  const portfolioQuery = useQuery({
    queryKey: reportQueryKeys.projectPortfolio(reportOptions),
    queryFn: () => getProjectPortfolioReport(reportOptions),
    enabled: tab === 12,
  });
  const timesheetExportQuery = useQuery({
    queryKey: ['reports', 'timesheet-export', exportPeriod, exportFilters],
    queryFn: () =>
      getTimesheetExportReport({
        period: exportPeriod,
        team_id: exportFilters.team_id || undefined,
        user_id: exportFilters.user_id || undefined,
        customer_id: exportFilters.customer_id || undefined,
        project_id: exportFilters.project_id || undefined,
        task_type_id: exportFilters.task_type_id || undefined,
        billable: exportFilters.billable || undefined,
      }),
    enabled: tab === 13,
  });

  const exportTeamsQuery = useQuery({
    queryKey: ['reports', 'export-teams'],
    queryFn: fetchTeams,
    enabled: tab === 13,
    staleTime: 5 * 60 * 1000,
  });
  const exportUsersQuery = useQuery({
    queryKey: ['reports', 'export-users'],
    queryFn: fetchUsers,
    enabled: tab === 13,
    staleTime: 5 * 60 * 1000,
  });
  const exportCustomersQuery = useQuery({
    queryKey: ['reports', 'export-customers'],
    queryFn: fetchCustomers,
    enabled: tab === 13,
    staleTime: 5 * 60 * 1000,
  });
  const exportProjectsQuery = useQuery({
    queryKey: ['reports', 'export-projects'],
    queryFn: () => fetchProjects({ limit: 500 }),
    enabled: tab === 13,
    staleTime: 5 * 60 * 1000,
  });
  const exportTaskTypesQuery = useQuery({
    queryKey: ['reports', 'export-task-types'],
    queryFn: () => fetchTaskTypes(),
    enabled: tab === 13,
    staleTime: 5 * 60 * 1000,
  });

  const teamReportsEnabled = tab === 14;

  const activeQuery = useMemo(() => {
    if (teamReportsEnabled) return { isLoading: false, error: null };
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
      stageSummaryQuery,
      executionSummaryQuery,
      portfolioQuery,
      timesheetExportQuery,
    ];
    return queries[tab] ?? projectHoursQuery;
  }, [
    tab,
    teamReportsEnabled,
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
    stageSummaryQuery,
    executionSummaryQuery,
    portfolioQuery,
  ]);

  const handleTabChange = (_: unknown, value: number) => {
    const config = TAB_CONFIG[value];
    setTab(value);
    setSearchParams({ tab: config.slug });
  };

  const handleCategoryChange = (next: ReportCategoryId | 'all') => {
    setAppliedCategory(next);
    if (next === 'all') return;
    const cat = REPORT_CATEGORIES.find((c) => c.id === next);
    if (!cat) return;
    const firstTab = TAB_CONFIG.findIndex((t) => (cat.slugs as readonly string[]).includes(t.slug));
    if (firstTab >= 0) {
      setTab(firstTab);
      setSearchParams({ tab: TAB_CONFIG[firstTab].slug });
    }
  };

  const activeFilterCount =
    (appliedCategory !== 'all' ? 1 : 0) +
    (!appliedIncludeArchived ? 1 : 0) +
    (appliedIncludeDeleted ? 1 : 0);

  const filterChips = useMemo(() => {
    const chips = [];
    if (appliedCategory !== 'all') {
      const label = REPORT_CATEGORIES.find((cat) => cat.id === appliedCategory)?.label ?? appliedCategory;
      chips.push({
        key: 'category',
        label: `Category: ${label}`,
        onRemove: () => {
          setAppliedCategory('all');
          setDraftCategory('all');
        },
      });
    }
    if (!appliedIncludeArchived) {
      chips.push({
        key: 'archived',
        label: 'Exclude archived',
        onRemove: () => {
          setAppliedIncludeArchived(true);
          setDraftIncludeArchived(true);
        },
      });
    }
    if (appliedIncludeDeleted) {
      chips.push({
        key: 'deleted',
        label: 'Include deleted',
        onRemove: () => {
          setAppliedIncludeDeleted(false);
          setDraftIncludeDeleted(false);
        },
      });
    }
    return chips;
  }, [appliedCategory, appliedIncludeArchived, appliedIncludeDeleted]);

  const applyFilters = () => {
    if (draftCategory !== appliedCategory) {
      handleCategoryChange(draftCategory);
    }
    setAppliedIncludeArchived(draftIncludeArchived);
    setAppliedIncludeDeleted(draftIncludeDeleted);
  };

  const resetFilters = () => {
    setDraftCategory('all');
    setDraftIncludeArchived(true);
    setDraftIncludeDeleted(false);
  };

  const clearFilters = () => {
    setAppliedCategory('all');
    setDraftCategory('all');
    setAppliedIncludeArchived(true);
    setDraftIncludeArchived(true);
    setAppliedIncludeDeleted(false);
    setDraftIncludeDeleted(false);
  };

  return (
    <PageContainer>
      <ModernPageHeader
        title="Reports & Analytics"
        subtitle="Visual dashboards with charts, filters, drill-down, and export"
      />

      <FilterToolbar
        sticky
        filterButton={{ activeCount: activeFilterCount, onClick: () => setFiltersOpen(true) }}
        chips={filterChips}
        onClearAll={clearFilters}
      />

      <Tabs
        value={tab}
        onChange={handleTabChange}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 2 }}
      >
        {(appliedCategory === 'all' ? TAB_CONFIG : visibleTabs).map((config) => {
          const index = TAB_CONFIG.findIndex((t) => t.slug === config.slug);
          return <Tab key={config.slug} value={index} label={config.label} />;
        })}
      </Tabs>

        {activeQuery.isLoading ? <LoadingState message="Loading reports…" /> : null}
        {activeQuery.error ? <ErrorState error={activeQuery.error} /> : null}

        {tab === 0 && !projectHoursQuery.isLoading && !projectHoursQuery.error ? (
          <ProjectHoursReportView rows={projectHoursQuery.data ?? []} canExport={canExport} />
        ) : null}

        {tab === 1 && !productiveQuery.isLoading && !productiveQuery.error ? (
          <SimpleTableReportView
            title="Productive Hours"
            filename="productive-hours"
            canExport={canExport}
            rows={(productiveQuery.data ?? []) as unknown as Record<string, unknown>[]}
            columns={[
              { key: 'tool_number', header: 'Project' },
              { key: 'customer_name', header: 'Customer' },
              { key: 'task_type_name', header: 'Task' },
              { key: 'total_hours', header: 'Total', align: 'right' },
              { key: 'billable_hours', header: 'Billable', align: 'right' },
              { key: 'non_billable_hours', header: 'Non-Billable', align: 'right' },
            ]}
          />
        ) : null}

        {tab === 2 && !npHoursQuery.isLoading && !npHoursQuery.error ? (
          <SimpleTableReportView
            title="NP Hours by Code"
            filename="np-hours-by-code"
            canExport={canExport}
            rows={(npHoursQuery.data ?? []).map((r) => ({
              ...r,
              total_hours: formatNumber(r.total_hours),
            })) as unknown as Record<string, unknown>[]}
            columns={[
              { key: 'non_productive_code', header: 'NP Code' },
              { key: 'description', header: 'Description' },
              { key: 'customer_name', header: 'Customer' },
              { key: 'total_hours', header: 'Hours', align: 'right' },
            ]}
          />
        ) : null}

        {tab === 3 && !npByDesignerQuery.isLoading && !npByDesignerQuery.error ? (
          <SimpleTableReportView
            title="NP Hours by Designer"
            filename="np-by-designer"
            canExport={canExport}
            rows={(npByDesignerQuery.data ?? []) as unknown as Record<string, unknown>[]}
            columns={[
              { key: 'designer_name', header: 'Designer' },
              { key: 'total_np_hours', header: 'NP Hours', align: 'right' },
            ]}
          />
        ) : null}

        {tab === 4 && !npTrendsQuery.isLoading && !npTrendsQuery.error ? (
          <NpTrendReportView rows={npTrendsQuery.data ?? []} canExport={canExport} />
        ) : null}

        {tab === 5 && !billableVsNpQuery.isLoading && !billableVsNpQuery.error && billableVsNpQuery.data ? (
          <BillableVsNpReportView data={billableVsNpQuery.data} canExport={canExport} />
        ) : null}

        {tab === 6 && !topNpQuery.isLoading && !topNpQuery.error ? (
          <SimpleTableReportView
            title="Top NP Activities"
            filename="top-np-activities"
            canExport={canExport}
            rows={(topNpQuery.data ?? []) as unknown as Record<string, unknown>[]}
            columns={[
              { key: 'non_productive_code', header: 'Code' },
              { key: 'description', header: 'Description' },
              { key: 'total_hours', header: 'Hours', align: 'right' },
              { key: 'entry_count', header: 'Entries', align: 'right' },
            ]}
          />
        ) : null}

        {tab === 7 && !billableQuery.isLoading && !billableQuery.error ? (
          <BillableUtilizationReportView rows={billableQuery.data ?? []} canExport={canExport} />
        ) : null}

        {tab === 8 && !designerQuery.isLoading && !designerQuery.error ? (
          <DesignerUtilizationReportView rows={designerQuery.data ?? []} canExport={canExport} />
        ) : null}

        {tab === 9 && !customerQuery.isLoading && !customerQuery.error ? (
          <CustomerSummaryReportView rows={customerQuery.data ?? []} canExport={canExport} />
        ) : null}

        {tab === 10 && !stageSummaryQuery.isLoading && !stageSummaryQuery.error ? (
          <StageSummaryReportView rows={stageSummaryQuery.data ?? []} canExport={canExport} />
        ) : null}

        {tab === 11 && !executionSummaryQuery.isLoading && !executionSummaryQuery.error ? (
          <ExecutionSummaryReportView rows={executionSummaryQuery.data ?? []} canExport={canExport} />
        ) : null}

        {tab === 12 && !portfolioQuery.isLoading && !portfolioQuery.error ? (
          <PortfolioReportView rows={portfolioQuery.data ?? []} canExport={canExport} />
        ) : null}

        {tab === 13 && !timesheetExportQuery.isLoading && !timesheetExportQuery.error ? (
          <Stack spacing={2}>
            <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap' }}>
              <FormSelect
                label="Export period"
                value={exportPeriod}
                options={[
                  { value: 'daily', label: 'Daily' },
                  { value: 'weekly', label: 'Weekly' },
                  { value: 'monthly', label: 'Monthly' },
                  { value: 'quarterly', label: 'Quarterly' },
                  { value: 'yearly', label: 'Yearly' },
                ]}
                onChange={(event) =>
                  setExportPeriod(event.target.value as typeof exportPeriod)
                }
                sx={compactFilterFieldSx}
              />
              <FormSelect
                label="Team"
                value={exportFilters.team_id}
                options={[
                  { value: '', label: 'All teams' },
                  ...(exportTeamsQuery.data ?? []).map((t) => ({ value: t.id, label: t.name })),
                ]}
                onChange={(event) =>
                  setExportFilters((f) => ({ ...f, team_id: String(event.target.value) }))
                }
                sx={compactFilterFieldSx}
              />
              <FormSelect
                label="Designer"
                value={exportFilters.user_id}
                options={[
                  { value: '', label: 'All designers' },
                  ...(exportUsersQuery.data ?? []).map((u) => ({
                    value: u.id,
                    label: `${u.first_name} ${u.last_name}`.trim() || u.email,
                  })),
                ]}
                onChange={(event) =>
                  setExportFilters((f) => ({ ...f, user_id: String(event.target.value) }))
                }
                sx={compactFilterFieldSx}
              />
              <FormSelect
                label="Customer"
                value={exportFilters.customer_id}
                options={[
                  { value: '', label: 'All customers' },
                  ...(exportCustomersQuery.data ?? []).map((c) => ({ value: c.id, label: c.name })),
                ]}
                onChange={(event) =>
                  setExportFilters((f) => ({ ...f, customer_id: String(event.target.value) }))
                }
                sx={compactFilterFieldSx}
              />
              <FormSelect
                label="Project"
                value={exportFilters.project_id}
                options={[
                  { value: '', label: 'All projects' },
                  ...(exportProjectsQuery.data ?? []).map((p) => ({
                    value: p.id,
                    label: p.code ? `${p.code} — ${p.tool_number}` : p.tool_number || p.id,
                  })),
                ]}
                onChange={(event) =>
                  setExportFilters((f) => ({ ...f, project_id: String(event.target.value) }))
                }
                sx={compactFilterFieldSx}
              />
              <FormSelect
                label="Task"
                value={exportFilters.task_type_id}
                options={[
                  { value: '', label: 'All tasks' },
                  ...(exportTaskTypesQuery.data ?? []).map((t) => ({ value: t.id, label: t.name })),
                ]}
                onChange={(event) =>
                  setExportFilters((f) => ({ ...f, task_type_id: String(event.target.value) }))
                }
                sx={compactFilterFieldSx}
              />
              <FormSelect
                label="Billable"
                value={exportFilters.billable}
                options={[
                  { value: '', label: 'All' },
                  { value: 'billable', label: 'Billable only' },
                  { value: 'non_billable', label: 'Non-billable only' },
                ]}
                onChange={(event) =>
                  setExportFilters((f) => ({
                    ...f,
                    billable: event.target.value as typeof f.billable,
                  }))
                }
                sx={compactFilterFieldSx}
              />
            </Stack>
            <SimpleTableReportView
              title="Timesheet Export"
              filename={`timesheet-export-${exportPeriod}`}
              canExport={canExport}
              rows={(timesheetExportQuery.data ?? []) as unknown as Record<string, unknown>[]}
              columns={[
                { key: 'entry_date', header: 'Date' },
                { key: 'employee_name', header: 'Employee' },
                { key: 'team_name', header: 'Team' },
                { key: 'customer_name', header: 'Customer' },
                { key: 'tool_number', header: 'Project' },
                { key: 'task_name', header: 'Task' },
                { key: 'hours', header: 'Hours', align: 'right' },
                { key: 'is_billable', header: 'Billable' },
                { key: 'work_category', header: 'Category' },
              ]}
            />
          </Stack>
        ) : null}

        {teamReportsEnabled ? <TeamReportsPanel reportOptions={reportOptions} /> : null}

      <FilterDrawer
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="Report filters"
        subtitle="Scope and data options"
        onApply={applyFilters}
        onReset={resetFilters}
      >
        <Stack spacing={1}>
          <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
            Primary filters
          </Typography>
          <Box sx={compactFilterFieldSx}>
            <FormSelect
              label="Category"
              size="small"
              value={draftCategory}
              options={[
                { value: 'all', label: 'All categories' },
                ...REPORT_CATEGORIES.map((cat) => ({ value: cat.id, label: cat.label })),
              ]}
              onChange={(event) =>
                setDraftCategory(event.target.value as ReportCategoryId | 'all')
              }
            />
          </Box>
        </Stack>
        <FilterGroup title="Advanced filters" icon={<TuneRoundedIcon sx={{ fontSize: 14 }} />}>
          <FormControlLabel
            sx={{ ml: 0, mr: 0 }}
            control={
              <Switch
                size="small"
                checked={draftIncludeArchived}
                onChange={(event) => setDraftIncludeArchived(event.target.checked)}
              />
            }
            label={<Typography variant="caption">Include archived</Typography>}
          />
          {canViewDeletedProjects(access) ? (
            <FormControlLabel
              sx={{ ml: 0, mr: 0 }}
              control={
                <Switch
                  size="small"
                  checked={draftIncludeDeleted}
                  onChange={(event) => setDraftIncludeDeleted(event.target.checked)}
                />
              }
              label={<Typography variant="caption">Include deleted (admin)</Typography>}
            />
          ) : null}
        </FilterGroup>
      </FilterDrawer>
    </PageContainer>
  );
}
