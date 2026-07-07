import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
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
import { ModernPageHeader } from '../components/ui/design-system';
import { ContentCard } from '../components/ui/cards';
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
  reportQueryKeys,
  type ReportOptions,
} from '../services/reportService';
import { accessContextFromUser, canExportReports, canViewDeletedProjects } from '../utils/permissions';
import { formatNumber } from '../utils/format';

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
  const [category, setCategory] = useState<ReportCategoryId | 'all'>('all');
  const { user } = useAuth();
  const [includeArchived, setIncludeArchived] = useState(true);
  const [includeDeleted, setIncludeDeleted] = useState(false);

  const access = accessContextFromUser(user);
  const canExport = canExportReports(access);

  useEffect(() => {
    setTab(tabIndexFromSlug(searchParams.get('tab')));
  }, [searchParams]);

  const reportOptions: ReportOptions = {
    include_archived: includeArchived,
    include_deleted: includeDeleted,
  };

  const visibleTabs = useMemo(() => {
    if (category === 'all') return TAB_CONFIG;
    const cat = REPORT_CATEGORIES.find((c) => c.id === category);
    if (!cat) return TAB_CONFIG;
    return TAB_CONFIG.filter((t) => (cat.slugs as readonly string[]).includes(t.slug));
  }, [category]);

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

  const teamReportsEnabled = tab === 13;

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
    setCategory(next);
    if (next === 'all') return;
    const cat = REPORT_CATEGORIES.find((c) => c.id === next);
    if (!cat) return;
    const firstTab = TAB_CONFIG.findIndex((t) => (cat.slugs as readonly string[]).includes(t.slug));
    if (firstTab >= 0) {
      setTab(firstTab);
      setSearchParams({ tab: TAB_CONFIG[firstTab].slug });
    }
  };

  return (
    <PageContainer>
      <ModernPageHeader
        title="Reports & Analytics"
        subtitle="Visual dashboards with charts, filters, drill-down, and export"
      />

      <Stack spacing={2.5}>
        <ContentCard>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
            Categories
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
            <Chip
              label="All"
              color={category === 'all' ? 'primary' : 'default'}
              onClick={() => handleCategoryChange('all')}
              variant={category === 'all' ? 'filled' : 'outlined'}
            />
            {REPORT_CATEGORIES.map((cat) => (
              <Chip
                key={cat.id}
                label={cat.label}
                color={category === cat.id ? 'primary' : 'default'}
                onClick={() => handleCategoryChange(cat.id)}
                variant={category === cat.id ? 'filled' : 'outlined'}
              />
            ))}
          </Box>
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
            {canViewDeletedProjects(access) ? (
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

        <Tabs
          value={tab}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
        >
          {(category === 'all' ? TAB_CONFIG : visibleTabs).map((config) => {
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

        {teamReportsEnabled ? <TeamReportsPanel reportOptions={reportOptions} /> : null}
      </Stack>
    </PageContainer>
  );
}
