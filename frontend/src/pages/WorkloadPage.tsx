import { useMemo, useState } from 'react';
import { Box, Stack, TableRow } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import AccessTimeRoundedIcon from '@mui/icons-material/AccessTimeRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import PaidRoundedIcon from '@mui/icons-material/PaidRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import { fetchDesignerWorkload } from '../api/dashboard';
import { fetchResourcePlanningGrid } from '../api/resourcePlanning';
import { fetchDashboardSummary } from '../api/dashboard';
import { fetchTeams } from '../api/lookups';
import { PageContainer } from '../components/common/PageContainer';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { AnalyticsBarChart } from '../components/analytics/AnalyticsCharts';
import { KpiStrip } from '../components/analytics/KpiStrip';
import { WorkloadHeatmap } from '../components/analytics/WorkloadHeatmap';
import {
  ClickableTableRow,
  DashboardPanel,
  EntityAvatar,
  FilterDrawer,
  FilterToolbar,
  FormSelect,
  KpiMetricCard,
  ModernPageHeader,
  OperationalDataTable,
  StickyHeaderCell,
  StickyTableCell,
  UtilizationBar,
  compactFilterFieldSx,
} from '../components/ui/design-system';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { formatDisplayValue, formatNumber, toFiniteNumber } from '../utils/format';

export function WorkloadPage() {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [appliedTeamFilter, setAppliedTeamFilter] = useState('all');
  const [draftTeamFilter, setDraftTeamFilter] = useState('all');

  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams'],
    queryFn: fetchTeams,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const workloadQuery = useQuery({
    queryKey: ['dashboard', 'workload'],
    queryFn: fetchDesignerWorkload,
  });

  const planningQuery = useQuery({
    queryKey: ['resource-planning', 'grid', { granularity: 'week' }],
    queryFn: () => fetchResourcePlanningGrid({ granularity: 'week' }),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const summaryQuery = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => fetchDashboardSummary(),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const teamNameMap = useMemo(
    () => new Map((teamsQuery.data ?? []).map((team) => [team.id, team.name])),
    [teamsQuery.data],
  );

  const designerTeamMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const designer of planningQuery.data?.designers ?? []) {
      if (designer.team_name) map.set(designer.user_id, designer.team_name);
    }
    return map;
  }, [planningQuery.data?.designers]);

  const filteredWorkload = useMemo(() => {
    const rows = workloadQuery.data ?? [];
    if (appliedTeamFilter === 'all') return rows;
    const teamName = teamNameMap.get(appliedTeamFilter);
    if (!teamName) return rows;
    return rows.filter((row) => designerTeamMap.get(row.user_id) === teamName);
  }, [appliedTeamFilter, designerTeamMap, teamNameMap, workloadQuery.data]);

  const filterChips = useMemo(() => {
    if (appliedTeamFilter === 'all') return [];
    return [
      {
        key: 'team',
        label: `Team: ${teamNameMap.get(appliedTeamFilter) ?? 'Unknown'}`,
        onRemove: () => {
          setAppliedTeamFilter('all');
          setDraftTeamFilter('all');
        },
      },
    ];
  }, [appliedTeamFilter, teamNameMap]);

  const heatmapData = useMemo(() => {
    const grid = planningQuery.data;
    if (!grid) return { rows: [] as string[], columns: [] as string[], cells: [] as import('../components/analytics/WorkloadHeatmap').HeatmapCell[] };

    const rows = grid.designers.map((d) => d.user_id);
    const rowLabels = Object.fromEntries(grid.designers.map((d) => [d.user_id, d.designer_name]));
    const columns = grid.periods.map((p) => p.key);
    const columnLabels = Object.fromEntries(grid.periods.map((p) => [p.key, p.label]));
    const cells = grid.designers.flatMap((designer) =>
      designer.cells.map((cell) => ({
        rowId: designer.user_id,
        rowLabel: designer.designer_name,
        columnId: cell.period_key,
        columnLabel: grid.periods.find((p) => p.key === cell.period_key)?.label ?? cell.period_key,
        value: cell.allocated_hours,
      })),
    );

    return { rows, columns, cells, rowLabels, columnLabels };
  }, [planningQuery.data]);

  const summary = useMemo(() => {
    const rows = filteredWorkload;
    const quoted = rows.reduce((s, r) => s + toFiniteNumber(r.quoted_hours_assigned), 0);
    const actual = rows.reduce((s, r) => s + toFiniteNumber(r.actual_hours_logged), 0);
    const weekHours = rows.reduce((s, r) => s + toFiniteNumber(r.hours_this_week), 0);
    const billable = toFiniteNumber(summaryQuery.data?.billable_hours);
    const nonBillable = toFiniteNumber(summaryQuery.data?.non_billable_hours);
    const np = toFiniteNumber(summaryQuery.data?.np_hours);
    const totalHours = billable + nonBillable + np;
    const billablePct =
      totalHours > 0
        ? Math.round((billable / totalHours) * 100)
        : Math.round(toFiniteNumber(summaryQuery.data?.productive_percent));
    const npPct = totalHours > 0 ? Math.round((np / totalHours) * 100) : 0;
    return { quoted, actual, weekHours, billablePct, npPct, count: rows.length };
  }, [filteredWorkload, summaryQuery.data]);

  const teamUtilization = useMemo(() => {
    const teams = planningQuery.data?.team_summary ?? [];
    if (appliedTeamFilter === 'all') return teams;
    const teamName = teamNameMap.get(appliedTeamFilter);
    return teams.filter((team) => team.team_name === teamName);
  }, [appliedTeamFilter, planningQuery.data?.team_summary, teamNameMap]);

  const monthlyForecast = useMemo(() => {
    const now = new Date();
    const labels = [0, 1, 2].map((offset) => {
      const d = new Date(now.getFullYear(), now.getMonth() + offset, 1);
      return d.toLocaleString('default', { month: 'short' });
    });
    const baseLoad = summary.actual || summary.quoted || 1;
    return {
      labels,
      values: [baseLoad, Math.round(baseLoad * 1.05), Math.round(baseLoad * 0.95)],
    };
  }, [summary.actual, summary.quoted]);

  if (workloadQuery.isLoading) return <LoadingState />;
  if (workloadQuery.error) return <ErrorState error={workloadQuery.error} />;

  const data = filteredWorkload;

  return (
    <PageContainer>
      <ModernPageHeader
        title="Workload Dashboard"
        subtitle="Designer heatmap, utilization summary, and team capacity forecasts"
      />

      <Box sx={{ mb: 2.5 }}>
        <KpiStrip columns={4}>
          <KpiMetricCard
            compact
            title="Designers"
            value={String(summary.count)}
            icon={GroupsRoundedIcon}
            accent="primary"
          />
          <KpiMetricCard
            compact
            title="Hours This Week"
            value={formatNumber(summary.weekHours, 1) || '0'}
            icon={AccessTimeRoundedIcon}
            accent="info"
          />
          <KpiMetricCard
            compact
            title="Billable %"
            value={`${formatNumber(summary.billablePct, 0) || '0'}%`}
            icon={PaidRoundedIcon}
            accent="success"
          />
          <KpiMetricCard
            compact
            title="NP Share"
            value={`${formatNumber(summary.npPct, 0) || '0'}%`}
            icon={TrendingUpRoundedIcon}
            accent="warning"
          />
        </KpiStrip>
      </Box>

      <FilterToolbar
        sticky
        filterButton={{
          activeCount: appliedTeamFilter !== 'all' ? 1 : 0,
          onClick: () => setFiltersOpen(true),
        }}
        chips={filterChips}
        onClearAll={() => {
          setAppliedTeamFilter('all');
          setDraftTeamFilter('all');
        }}
      />

      {!data.length ? (
        <EmptyState
          title="No workload data"
          description="Designers will appear here once projects are assigned."
        />
      ) : (
        <Stack spacing={3}>
          <DashboardPanel title="Workload Heatmap" subtitle="Allocated hours by designer and week">
            {planningQuery.isLoading ? (
              <LoadingState message="Loading heatmap…" />
            ) : heatmapData.rows.length ? (
              <WorkloadHeatmap
                rows={heatmapData.rows}
                columns={heatmapData.columns}
                cells={heatmapData.cells}
                rowLabels={heatmapData.rowLabels}
                columnLabels={heatmapData.columnLabels}
              />
            ) : (
              <EmptyState title="No planning data" description="Resource planning grid is empty for this week." />
            )}
          </DashboardPanel>

          <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2}>
            <Box sx={{ flex: 1 }}>
            <DashboardPanel title="Team Utilization" subtitle="Current load vs capacity">
              <Stack spacing={1.5}>
                {teamUtilization.map((team) => (
                  <div key={team.team_id}>
                    <UtilizationBar
                      label={team.team_name}
                      value={team.utilization_percent}
                      showValue
                    />
                    <span style={{ fontSize: '0.7rem', color: 'var(--mui-palette-text-secondary)' }}>
                      {formatNumber(team.allocated_hours)}h allocated ·{' '}
                      {formatNumber(team.remaining_capacity_hours)}h remaining
                    </span>
                  </div>
                ))}
                {!teamUtilization.length ? (
                  <span style={{ color: 'var(--mui-palette-text-secondary)' }}>No team data available.</span>
                ) : null}
              </Stack>
            </DashboardPanel>
            </Box>

            <Box sx={{ flex: 1 }}>
            <DashboardPanel title="Monthly Forecast" subtitle="Projected workload (estimated)">
              <AnalyticsBarChart
                categories={monthlyForecast.labels}
                series={[{ label: 'Forecast hours', data: monthlyForecast.values }]}
                height={220}
              />
            </DashboardPanel>
            </Box>
          </Stack>

          <DashboardPanel title="Designer Workload" subtitle="Detailed allocation and logging" noPadding>
            <OperationalDataTable
              maxHeight={480}
              head={
                <TableRow>
                  <StickyHeaderCell pinned>Designer</StickyHeaderCell>
                  <StickyHeaderCell>Role</StickyHeaderCell>
                  <StickyHeaderCell align="right">Active Projects</StickyHeaderCell>
                  <StickyHeaderCell align="right">Hours This Week</StickyHeaderCell>
                  <StickyHeaderCell>Utilization</StickyHeaderCell>
                  <StickyHeaderCell align="right">Quoted Assigned</StickyHeaderCell>
                  <StickyHeaderCell align="right">Actual Logged</StickyHeaderCell>
                </TableRow>
              }
            >
              {data.map((row) => {
                const utilization =
                  row.quoted_hours_assigned > 0
                    ? Math.round((row.actual_hours_logged / row.quoted_hours_assigned) * 100)
                    : 0;
                return (
                  <ClickableTableRow key={row.user_id}>
                    <StickyTableCell pinned>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                        <EntityAvatar label={row.designer_name} size={28} />
                        {formatDisplayValue(row.designer_name)}
                      </span>
                    </StickyTableCell>
                    <StickyTableCell>{formatDisplayValue(row.role)}</StickyTableCell>
                    <StickyTableCell align="right">{row.active_projects}</StickyTableCell>
                    <StickyTableCell align="right">{formatNumber(row.hours_this_week)}</StickyTableCell>
                    <StickyTableCell>
                      <UtilizationBar label="" value={utilization} showValue />
                    </StickyTableCell>
                    <StickyTableCell align="right">{formatNumber(row.quoted_hours_assigned)}</StickyTableCell>
                    <StickyTableCell align="right">{formatNumber(row.actual_hours_logged)}</StickyTableCell>
                  </ClickableTableRow>
                );
              })}
            </OperationalDataTable>
          </DashboardPanel>
        </Stack>
      )}

      <FilterDrawer
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="Workload filters"
        onApply={() => setAppliedTeamFilter(draftTeamFilter)}
        onReset={() => setDraftTeamFilter('all')}
      >
        <Box sx={compactFilterFieldSx}>
          <FormSelect
            label="Team"
            size="small"
            value={draftTeamFilter}
            options={[
              { value: 'all', label: 'All Teams' },
              ...(teamsQuery.data ?? []).map((team) => ({ value: team.id, label: team.name })),
            ]}
            onChange={(event) => setDraftTeamFilter(String(event.target.value))}
          />
        </Box>
      </FilterDrawer>
    </PageContainer>
  );
}
