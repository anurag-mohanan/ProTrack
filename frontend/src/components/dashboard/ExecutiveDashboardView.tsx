import { Box, Button, Grid, Stack, Typography } from '@mui/material';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { ActivityTimeline } from './ActivityTimeline';
import { ProjectHealthChart, ProjectStageChart, CustomerWorkloadChart, HoursSummaryChart } from './DashboardCharts';
import { buildExecutiveKpis, ExecutiveKpiGrid } from './ExecutiveKpiGrid';
import { CustomerWorkloadWidget } from './CustomerWorkloadWidget';
import { DashboardKpiSkeleton, DashboardPanelSkeleton } from './DashboardSkeletons';
import { DesignerUtilizationList } from './DesignerUtilizationList';
import { ProjectHealthSummary } from './ProjectHealthSummary';
import { ProjectStageCards } from './ProjectStageCards';
import { ProjectsAttentionTable } from './ProjectsAttentionTable';
import { designTokens } from '../../theme/designTokens';
import { formatNumber } from '../../utils/format';

interface ExecutiveDashboardViewProps {
  summary: DashboardSummary | undefined;
  unavailable: boolean;
  loading: boolean;
  navigate: NavigateFunction;
  isAdmin?: boolean;
}

export function ExecutiveDashboardView({
  summary,
  unavailable,
  loading,
  navigate,
  isAdmin = false,
}: ExecutiveDashboardViewProps) {
  const executiveKpis = buildExecutiveKpis({ summary, unavailable, navigate });
  const attentionRows = summary?.attention_projects ?? [];
  const upcomingDeliveries = attentionRows.filter((row) => row.attention_reason === 'due_soon');
  const delayedProjects = attentionRows.filter((row) => row.attention_reason === 'overdue');
  const importActivities = (summary?.activity_feed ?? []).filter((a) => a.category === 'import');
  const systemActivities = isAdmin
    ? (summary?.activity_feed ?? []).filter((a) => a.category === 'import' || a.category === 'user')
    : [];

  const greyHealth = Math.max(
    0,
    (summary?.active_projects ?? 0) -
      (summary?.green_projects ?? 0) -
      (summary?.yellow_projects ?? 0) -
      (summary?.red_projects ?? 0),
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {loading ? <DashboardKpiSkeleton count={7} /> : <ExecutiveKpiGrid cards={executiveKpis} />}

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, lg: 8 }}>
          {loading ? (
            <DashboardPanelSkeleton height={320} />
          ) : (
            <DashboardPanel
              title="Current Customer Workload"
              subtitle="Active tools, designers, and hours by customer"
              action={
                <Button
                  size="small"
                  endIcon={<ArrowForwardRoundedIcon />}
                  onClick={() => navigate('/projects')}
                  sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
                >
                  All Projects
                </Button>
              }
              noPadding
            >
              <CustomerWorkloadWidget rows={summary?.customer_workload ?? []} showWorkloadPercent />
            </DashboardPanel>
          )}
        </Grid>
        <Grid size={{ xs: 12, lg: 4 }}>
          {loading ? (
            <DashboardPanelSkeleton height={320} />
          ) : (
            <DashboardPanel title="Project Health" subtitle="Portfolio risk distribution">
              <ProjectHealthChart
                green={summary?.green_projects ?? 0}
                yellow={summary?.yellow_projects ?? 0}
                red={summary?.red_projects ?? 0}
                grey={greyHealth}
              />
            </DashboardPanel>
          )}
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 6 }}>
          {loading ? (
            <DashboardPanelSkeleton height={280} />
          ) : (
            <DashboardPanel title="Customer Hours" subtitle="Top customers by logged hours">
              <CustomerWorkloadChart rows={summary?.customer_workload ?? []} height={240} />
            </DashboardPanel>
          )}
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          {loading ? (
            <DashboardPanelSkeleton height={280} />
          ) : (
            <DashboardPanel title="Hours Breakdown" subtitle="Billable vs non-productive portfolio hours">
              <HoursSummaryChart
                billableHours={summary?.billable_hours ?? 0}
                nonBillableHours={summary?.non_billable_hours ?? 0}
                npHours={summary?.np_hours ?? 0}
                height={240}
              />
            </DashboardPanel>
          )}
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 6 }}>
          {loading ? (
            <DashboardPanelSkeleton height={280} />
          ) : (
            <DashboardPanel title="Projects by Stage" subtitle="Distribution across engineering phases">
              <ProjectStageChart rows={summary?.projects_by_stage ?? []} height={240} />
            </DashboardPanel>
          )}
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          {loading ? (
            <DashboardPanelSkeleton height={280} />
          ) : (
            <DashboardPanel title="Stage Summary" subtitle="Quick count by phase">
              <ProjectStageCards rows={summary?.projects_by_stage ?? []} />
            </DashboardPanel>
          )}
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, lg: 7 }}>
          {loading ? (
            <DashboardPanelSkeleton height={280} />
          ) : (
            <DashboardPanel title="Resource Utilization" subtitle="Designer loading based on current assignments">
              <DesignerUtilizationList rows={summary?.designer_availability ?? []} limit={8} />
            </DashboardPanel>
          )}
        </Grid>
        <Grid size={{ xs: 12, lg: 5 }}>
          {loading ? (
            <DashboardPanelSkeleton height={280} />
          ) : (
            <DashboardPanel title="Health Overview" subtitle="At-a-glance portfolio status">
              {summary ? <ProjectHealthSummary summary={summary} /> : null}
            </DashboardPanel>
          )}
        </Grid>
      </Grid>

      {isAdmin ? (
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 4 }}>
            <DashboardPanel title="System Activity" subtitle="Operational metrics">
              <Stack spacing={1.5}>
                <MetricRow
                  label="Pending Timesheet Approvals"
                  value={formatNumber(summary?.operational_metrics?.pending_timesheet_approvals ?? 0, 0)}
                />
                <MetricRow
                  label="Pending Import Jobs"
                  value={formatNumber(summary?.operational_metrics?.pending_import_jobs ?? 0, 0)}
                />
                <MetricRow
                  label="Pending Project Approvals"
                  value={formatNumber(summary?.operational_metrics?.pending_project_approvals ?? 0, 0)}
                />
              </Stack>
            </DashboardPanel>
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <DashboardPanel title="Recent Imports & User Activity" subtitle="System administration events">
              <ActivityTimeline activities={systemActivities.slice(0, 8)} />
            </DashboardPanel>
          </Grid>
        </Grid>
      ) : null}

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, lg: 6 }}>
          {loading ? (
            <DashboardPanelSkeleton height={240} />
          ) : (
            <DashboardPanel title="Upcoming Deliveries" subtitle="Due within 7 days" noPadding>
              <ProjectsAttentionTable
                rows={upcomingDeliveries}
                filterLabel="upcoming deliveries"
                viewAllHref="/projects?due=7days"
              />
            </DashboardPanel>
          )}
        </Grid>
        <Grid size={{ xs: 12, lg: 6 }}>
          {loading ? (
            <DashboardPanelSkeleton height={240} />
          ) : (
            <DashboardPanel title="Delayed Projects" subtitle="Past due date" noPadding>
              <ProjectsAttentionTable
                rows={delayedProjects}
                filterLabel="delayed projects"
                viewAllHref="/projects?due=overdue"
              />
            </DashboardPanel>
          )}
        </Grid>
      </Grid>

      <DashboardPanel
        title={isAdmin ? 'System Activity Timeline' : 'Recent Activity'}
        subtitle={
          isAdmin
            ? `${importActivities.length} recent import events`
            : 'Latest updates across projects and teams'
        }
      >
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <ActivityTimeline activities={summary?.activity_feed ?? []} />
        )}
      </DashboardPanel>
    </Box>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        py: 1,
        px: 1.5,
        borderRadius: `${designTokens.radius.md}px`,
        bgcolor: designTokens.semantic.neutralSoft,
      }}
    >
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 800 }}>
        {value}
      </Typography>
    </Box>
  );
}
