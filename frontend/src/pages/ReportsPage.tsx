import { useEffect, useMemo, useState } from 'react';
import {
  FormControlLabel,
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
  ModernPageHeader,
} from '../components/ui/design-system';
import { ProjectHoursReportView } from '../components/reports/ReportAnalyticsViews';
import { TeamReportsPanel } from '../components/reports/TeamReportsPanel';
import { EngineeringReportingSuite } from '../components/reports/EngineeringReportingSuite';
import { CustomerTimesheetPackPanel } from '../components/reports/CustomerTimesheetPackPanel';
import { DesignerTeamTimesheetPanel } from '../components/reports/DesignerTeamTimesheetPanel';
import { useAuth } from '../context/AuthContext';
import {
  getProjectHoursReport,
  reportQueryKeys,
  type ReportOptions,
} from '../services/reportService';
import type { ProjectHoursReportRow } from '../types/Reports';
import { accessContextFromUser, canExportReports, canViewDeletedProjects } from '../utils/permissions';
import { ensureArray } from '../types/pagination';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';

/**
 * Keep Reports lean: only high-value operational reports.
 * Legacy tab slugs redirect here so old bookmarks do not crash.
 */
const TAB_CONFIG = [
  { label: 'Timesheet Reports', slug: 'timesheet-reports' },
  { label: 'Engineering Overview', slug: 'engineering-suite' },
  { label: 'Project Hours', slug: 'project-hours' },
  { label: 'Team Reports', slug: 'team-reports' },
  { label: 'Customer Timesheet Pack', slug: 'customer-timesheet-pack' },
] as const;

type TabSlug = (typeof TAB_CONFIG)[number]['slug'];

const TAB_SLUG_ALIASES: Record<string, TabSlug> = {
  'timesheet-export': 'timesheet-reports',
  'productive-hours': 'timesheet-reports',
  'np-hours': 'timesheet-reports',
  'np-by-designer': 'timesheet-reports',
  'np-by-month': 'timesheet-reports',
  'billable-vs-np': 'engineering-suite',
  'top-np': 'engineering-suite',
  'billable-utilization': 'team-reports',
  'designer-utilization': 'team-reports',
  'customer-summary': 'customer-timesheet-pack',
  'by-stage': 'project-hours',
  'by-execution-status': 'project-hours',
  'project-portfolio': 'project-hours',
};

function resolveTabSlug(slug: string | null): TabSlug | null {
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
    if (raw && !resolved) {
      setSearchParams({ tab: TAB_CONFIG[0].slug }, { replace: true });
      return;
    }
    setTab(tabIndexFromSlug(raw));
  }, [searchParams, setSearchParams]);

  const reportOptions: ReportOptions = {
    include_archived: appliedIncludeArchived,
    include_deleted: appliedIncludeDeleted,
  };

  const projectHoursQuery = useQuery({
    queryKey: reportQueryKeys.projectHours(reportOptions),
    queryFn: () => getProjectHoursReport(reportOptions),
    enabled: tab === 2,
  });

  const timesheetReportsEnabled = tab === 0;
  const suiteEnabled = tab === 1;
  const projectHoursEnabled = tab === 2;
  const teamReportsEnabled = tab === 3;
  const customerTimesheetPackEnabled = tab === 4;

  const handleTabChange = (_: unknown, value: number) => {
    const config = TAB_CONFIG[value];
    setTab(value);
    setSearchParams({ tab: config.slug });
  };

  const activeFilterCount =
    (!appliedIncludeArchived ? 1 : 0) + (appliedIncludeDeleted ? 1 : 0);

  const filterChips = useMemo(() => {
    const chips = [];
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
  }, [appliedIncludeArchived, appliedIncludeDeleted]);

  const applyFilters = () => {
    setAppliedIncludeArchived(draftIncludeArchived);
    setAppliedIncludeDeleted(draftIncludeDeleted);
  };

  const resetFilters = () => {
    setDraftIncludeArchived(true);
    setDraftIncludeDeleted(false);
  };

  const clearFilters = () => {
    setAppliedIncludeArchived(true);
    setDraftIncludeArchived(true);
    setAppliedIncludeDeleted(false);
    setDraftIncludeDeleted(false);
  };

  return (
    <PageContainer>
      <ModernPageHeader
        title="Reports"
        subtitle="Timesheets, engineering overview, project hours, teams, and customer packs"
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
        {TAB_CONFIG.map((config) => {
          const index = TAB_CONFIG.findIndex((t) => t.slug === config.slug);
          return <Tab key={config.slug} value={index} label={config.label} />;
        })}
      </Tabs>

      {projectHoursEnabled && projectHoursQuery.isLoading ? (
        <LoadingState message="Loading reports…" />
      ) : null}
      {projectHoursEnabled && projectHoursQuery.error ? (
        <ErrorState error={projectHoursQuery.error} />
      ) : null}

      {timesheetReportsEnabled ? (
        <DesignerTeamTimesheetPanel
          canExport={canExport}
          includeArchived={appliedIncludeArchived}
          includeDeleted={appliedIncludeDeleted}
        />
      ) : null}

      {suiteEnabled ? (
        <EngineeringReportingSuite
          canExport={canExport}
          includeArchived={appliedIncludeArchived}
          includeDeleted={appliedIncludeDeleted}
        />
      ) : null}

      {projectHoursEnabled && !projectHoursQuery.isLoading && !projectHoursQuery.error ? (
        <ProjectHoursReportView
          rows={ensureArray<ProjectHoursReportRow>(projectHoursQuery.data)}
          canExport={canExport}
        />
      ) : null}

      {teamReportsEnabled ? <TeamReportsPanel reportOptions={reportOptions} /> : null}
      {customerTimesheetPackEnabled ? <CustomerTimesheetPackPanel canExport={canExport} /> : null}

      <FilterDrawer
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="Report filters"
        subtitle="Data scope options"
        onApply={applyFilters}
        onReset={resetFilters}
      >
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
