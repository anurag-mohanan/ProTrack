import { Box } from '@mui/material';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { CustomerWorkloadWidget } from './CustomerWorkloadWidget';
import { DashboardSection } from './DashboardCards';
import { DashboardKpiSkeleton, DashboardPanelSkeleton } from './DashboardSkeletons';
import { buildExecutiveKpis, ExecutiveKpiGrid } from './ExecutiveKpiGrid';
import { ProjectsAttentionTable } from './ProjectsAttentionTable';
import { ProjectsByStageWidget } from './ProjectsByStageWidget';
import { RecentActivityWidget } from './RecentActivityWidget';
import { ResourcePlanningSummary } from './ResourcePlanningSummary';

interface ExecutiveDashboardViewProps {
  summary: DashboardSummary | undefined;
  unavailable: boolean;
  loading: boolean;
  navigate: NavigateFunction;
}

export function ExecutiveDashboardView({
  summary,
  unavailable,
  loading,
  navigate,
}: ExecutiveDashboardViewProps) {
  const executiveKpis = buildExecutiveKpis({ summary, unavailable, navigate });
  const attentionRows = summary?.attention_projects ?? [];
  const upcomingDeliveries = attentionRows.filter((row) => row.attention_reason === 'due_soon');
  const delayedProjects = attentionRows.filter((row) => row.attention_reason === 'overdue');

  return (
    <>
      {loading ? (
        <DashboardKpiSkeleton count={6} />
      ) : (
        <ExecutiveKpiGrid cards={executiveKpis} />
      )}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' },
          gap: 3,
          mb: 3,
        }}
      >
        <DashboardSection
          title="Active Projects by Stage"
          subtitle="Planning, in progress, and on hold"
        >
          {loading ? (
            <DashboardPanelSkeleton height={240} />
          ) : (
            <ProjectsByStageWidget rows={summary?.projects_by_stage ?? []} />
          )}
        </DashboardSection>

        <DashboardSection title="Resource Loading" subtitle="Team capacity and utilization">
          {loading ? (
            <DashboardPanelSkeleton height={240} />
          ) : (
            <ResourcePlanningSummary rows={summary?.team_summary ?? []} showHeader={false} />
          )}
        </DashboardSection>
      </Box>

      <DashboardSection
        title="Current Customer Workload"
        subtitle="Active tools in progress and assigned designers per customer"
      >
        {loading ? (
          <DashboardPanelSkeleton height={220} />
        ) : (
          <CustomerWorkloadWidget rows={summary?.customer_workload ?? []} compact />
        )}
      </DashboardSection>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' },
          gap: 3,
          mb: 3,
        }}
      >
        <DashboardSection title="Upcoming Deliveries" subtitle="Projects due within 7 days">
          {loading ? (
            <DashboardPanelSkeleton height={220} />
          ) : (
            <ProjectsAttentionTable
              rows={upcomingDeliveries}
              filterLabel="upcoming deliveries"
              viewAllHref="/projects?due=7days"
            />
          )}
        </DashboardSection>

        <DashboardSection title="Delayed Projects" subtitle="Projects past their due date">
          {loading ? (
            <DashboardPanelSkeleton height={220} />
          ) : (
            <ProjectsAttentionTable
              rows={delayedProjects}
              filterLabel="delayed projects"
              viewAllHref="/projects?due=overdue"
            />
          )}
        </DashboardSection>
      </Box>

      <DashboardSection title="Recent Activity" subtitle="Latest updates across projects and teams">
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <RecentActivityWidget activities={summary?.activity_feed ?? []} />
        )}
      </DashboardSection>
    </>
  );
}
