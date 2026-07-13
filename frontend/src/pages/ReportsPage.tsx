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
import { EngineeringReportingSuite } from '../components/reports/EngineeringReportingSuite';
import { CustomerTimesheetPackPanel } from '../components/reports/CustomerTimesheetPackPanel';
import { DesignerTeamTimesheetPanel } from '../components/reports/DesignerTeamTimesheetPanel';
import { useAuth } from '../context/AuthContext';
import {
  getBillableUtilizationReport,
  getBillableVsNonBillableReport,
  getCustomerSummaryReport,
  getDesignerUtilizationReport,
  getMonthlyNpTrendsReport,
  getNonProductiveHoursReport,
  getNpHoursByDesignerReport,
  getProjectHoursReport,
  getProjectPortfolioReport,
  getProjectStageSummaryReport,
  getExecutionStatusSummaryReport,
  getTopNpActivitiesReport,
  reportQueryKeys,
  type ReportOptions,
} from '../services/reportService';
import { accessContextFromUser, canExportReports, canViewDeletedProjects } from '../utils/permissions';
import { formatNumber } from '../utils/format';
import { ensureArray } from '../types/pagination';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';

const TAB_CONFIG = [
  { label: 'Engineering Suite', slug: 'engineering-suite', category: 'executive' },
  { label: 'Project Hours', slug: 'project-hours', category: 'projects' },
  { label: 'Timesheet Reports', slug: 'timesheet-reports', category: 'timesheets' },
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
  { label: 'Team Reports', slug: 'team-reports', category: 'planning' },
  { label: 'Customer Timesheet Pack', slug: 'customer-timesheet-pack', category: 'customers' },
] as const;

/** Legacy bookmarks from before Timesheet Reports was simplified. */
const TAB_SLUG_ALIASES: Record<string, (typeof TAB_CONFIG)[number]['slug']> = {
  'timesheet-export': 'timesheet-reports',
  'productive-hours': 'timesheet-reports',
};

function resolveTabSlug(slug: string | null): (typeof TAB_CONFIG)[number]['slug'] | null {
  if (!slug) return null;
  if (slug in TAB_SLUG_ALIASES) {
    return TAB_SLUG_ALIASES[slug];
  }
  const match = TAB_CONFIG.find((tab) => tab.slug === slug);
  return match?.slug ?? null;
}

function tabIndexFromSlug(slug: string | null): number {
  const resolved = resolveTabSlug(slug);
  if (!resolved) return 0;
  const index = TAB_CONFIG.findIndex((tab) => tab.slug === resolved);
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

  const access = accessContextFromUser(user);
  const canExport = canExportReports(access);

  useEffect(() => {
    const raw = searchParams.get('tab');
    const resolved = resolveTabSlug(raw);
    if (raw && resolved && raw !== resolved) {
      setSearchParams({ tab: resolved }, { replace: true });
      return;
    }
    setTab(tabIndexFromSlug(raw));
  }, [searchParams, setSearchParams]);

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
    enabled: tab === 1,
  });
  const npHoursQuery = useQuery({
    queryKey: reportQueryKeys.nonProductiveHours,
    queryFn: getNonProductiveHoursReport,
    enabled: tab === 3,
  });
  const npByDesignerQuery = useQuery({
    queryKey: reportQueryKeys.npHoursByDesigner,
    queryFn: getNpHoursByDesignerReport,
    enabled: tab === 4,
  });
  const npTrendsQuery = useQuery({
    queryKey: reportQueryKeys.monthlyNpTrends,
    queryFn: getMonthlyNpTrendsReport,
    enabled: tab === 5,
  });
  const billableVsNpQuery = useQuery({
    queryKey: reportQueryKeys.billableVsNonBillable,
    queryFn: getBillableVsNonBillableReport,
    enabled: tab === 6,
  });
  const topNpQuery = useQuery({
    queryKey: reportQueryKeys.topNpActivities,
    queryFn: getTopNpActivitiesReport,
    enabled: tab === 7,
  });
  const billableQuery = useQuery({
    queryKey: reportQueryKeys.billableUtilization,
    queryFn: getBillableUtilizationReport,
    enabled: tab === 8,
  });
  const designerQuery = useQuery({
    queryKey: reportQueryKeys.designerUtilization,
    queryFn: getDesignerUtilizationReport,
    enabled: tab === 9,
  });
  const customerQuery = useQuery({
    queryKey: reportQueryKeys.customerSummary(reportOptions),
    queryFn: () => getCustomerSummaryReport(reportOptions),
    enabled: tab === 10,
  });
  const stageSummaryQuery = useQuery({
    queryKey: reportQueryKeys.projectStageSummary(reportOptions),
    queryFn: () => getProjectStageSummaryReport(reportOptions),
    enabled: tab === 11,
  });
  const executionSummaryQuery = useQuery({
    queryKey: reportQueryKeys.executionStatusSummary(reportOptions),
    queryFn: () => getExecutionStatusSummaryReport(reportOptions),
    enabled: tab === 12,
  });
  const portfolioQuery = useQuery({
    queryKey: reportQueryKeys.projectPortfolio(reportOptions),
    queryFn: () => getProjectPortfolioReport(reportOptions),
    enabled: tab === 13,
  });

  const teamReportsEnabled = tab === 14;
  const customerTimesheetPackEnabled = tab === 15;
  const timesheetReportsEnabled = tab === 2;
  const suiteEnabled = tab === 0;

  const activeQuery = useMemo(() => {
    if (suiteEnabled || timesheetReportsEnabled || teamReportsEnabled || customerTimesheetPackEnabled) {
      return { isLoading: false, error: null };
    }
    const queries = [
      projectHoursQuery,
      null, // timesheet-reports
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
    ];
    return queries[tab - 1] ?? projectHoursQuery;
  }, [
    tab,
    suiteEnabled,
    timesheetReportsEnabled,
    teamReportsEnabled,
    customerTimesheetPackEnabled,
    projectHoursQuery,
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

        {suiteEnabled ? (
          <EngineeringReportingSuite
            canExport={canExport}
            includeArchived={appliedIncludeArchived}
            includeDeleted={appliedIncludeDeleted}
          />
        ) : null}

        {timesheetReportsEnabled ? (
          <DesignerTeamTimesheetPanel
            canExport={canExport}
            includeArchived={appliedIncludeArchived}
            includeDeleted={appliedIncludeDeleted}
          />
        ) : null}

        {tab === 1 && !projectHoursQuery.isLoading && !projectHoursQuery.error ? (
          <ProjectHoursReportView
            rows={ensureArray(projectHoursQuery.data)}
            canExport={canExport}
          />
        ) : null}

        {tab === 3 && !npHoursQuery.isLoading && !npHoursQuery.error ? (
          <SimpleTableReportView
            title="NP Hours by Code"
            filename="np-hours-by-code"
            canExport={canExport}
            rows={ensureArray(npHoursQuery.data).map((r) => ({
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

        {tab === 4 && !npByDesignerQuery.isLoading && !npByDesignerQuery.error ? (
          <SimpleTableReportView
            title="NP Hours by Designer"
            filename="np-by-designer"
            canExport={canExport}
            rows={ensureArray(npByDesignerQuery.data) as unknown as Record<string, unknown>[]}
            columns={[
              { key: 'designer_name', header: 'Designer' },
              { key: 'total_np_hours', header: 'NP Hours', align: 'right' },
            ]}
          />
        ) : null}

        {tab === 5 && !npTrendsQuery.isLoading && !npTrendsQuery.error ? (
          <NpTrendReportView rows={ensureArray(npTrendsQuery.data)} canExport={canExport} />
        ) : null}

        {tab === 6 && !billableVsNpQuery.isLoading && !billableVsNpQuery.error && billableVsNpQuery.data ? (
          <BillableVsNpReportView data={billableVsNpQuery.data} canExport={canExport} />
        ) : null}

        {tab === 7 && !topNpQuery.isLoading && !topNpQuery.error ? (
          <SimpleTableReportView
            title="Top NP Activities"
            filename="top-np-activities"
            canExport={canExport}
            rows={ensureArray(topNpQuery.data) as unknown as Record<string, unknown>[]}
            columns={[
              { key: 'non_productive_code', header: 'Code' },
              { key: 'description', header: 'Description' },
              { key: 'total_hours', header: 'Hours', align: 'right' },
              { key: 'entry_count', header: 'Entries', align: 'right' },
            ]}
          />
        ) : null}

        {tab === 8 && !billableQuery.isLoading && !billableQuery.error ? (
          <BillableUtilizationReportView rows={ensureArray(billableQuery.data)} canExport={canExport} />
        ) : null}

        {tab === 9 && !designerQuery.isLoading && !designerQuery.error ? (
          <DesignerUtilizationReportView rows={ensureArray(designerQuery.data)} canExport={canExport} />
        ) : null}

        {tab === 10 && !customerQuery.isLoading && !customerQuery.error ? (
          <CustomerSummaryReportView rows={ensureArray(customerQuery.data)} canExport={canExport} />
        ) : null}

        {tab === 11 && !stageSummaryQuery.isLoading && !stageSummaryQuery.error ? (
          <StageSummaryReportView rows={ensureArray(stageSummaryQuery.data)} canExport={canExport} />
        ) : null}

        {tab === 12 && !executionSummaryQuery.isLoading && !executionSummaryQuery.error ? (
          <ExecutionSummaryReportView
            rows={ensureArray(executionSummaryQuery.data)}
            canExport={canExport}
          />
        ) : null}

        {tab === 13 && !portfolioQuery.isLoading && !portfolioQuery.error ? (
          <PortfolioReportView rows={ensureArray(portfolioQuery.data)} canExport={canExport} />
        ) : null}

        {teamReportsEnabled ? <TeamReportsPanel reportOptions={reportOptions} /> : null}
        {customerTimesheetPackEnabled ? <CustomerTimesheetPackPanel canExport={canExport} /> : null}

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
