import { Grid } from '@mui/material';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { DashboardPanelSkeleton } from './DashboardSkeletons';
import {
  CustomerWorkloadChart,
  HoursSummaryChart,
  ProjectHealthChart,
  ProjectStageChart,
} from './DashboardCharts';
import { DesignerUtilizationList } from './DesignerUtilizationList';
import { ResourceAvailabilityPanel } from './ResourceAvailabilityPanel';

interface DashboardChartsSectionProps {
  summary: DashboardSummary | undefined;
  loading: boolean;
  navigate: NavigateFunction;
  showEngineeringCharts?: boolean;
}

export function DashboardChartsSection({
  summary,
  loading,
  showEngineeringCharts = true,
}: DashboardChartsSectionProps) {
  if (!showEngineeringCharts) return null;

  const greyHealth = Math.max(
    0,
    (summary?.active_projects ?? 0) -
      (summary?.green_projects ?? 0) -
      (summary?.yellow_projects ?? 0) -
      (summary?.red_projects ?? 0),
  );

  const panelSx = { height: 300 };

  return (
    <Grid container spacing={2} sx={{ mt: 0.5 }}>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            variant="minimal"
            title="Customer Workload"
            subtitle="Top customers by hours logged"
            height={panelSx.height}
          >
            <CustomerWorkloadChart rows={summary?.customer_workload ?? []} />
          </DashboardPanel>
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            variant="minimal"
            title="Designer Utilization"
            subtitle="Loading by assignment status"
            height={panelSx.height}
          >
            <DesignerUtilizationList rows={summary?.designer_availability ?? []} limit={5} />
          </DashboardPanel>
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            variant="minimal"
            title="Hours Burn"
            subtitle="Composition of logged hours"
            height={panelSx.height}
          >
            <HoursSummaryChart
              billableHours={summary?.billable_hours ?? 0}
              nonBillableHours={summary?.non_billable_hours ?? 0}
              npHours={summary?.np_hours ?? 0}
            />
          </DashboardPanel>
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            variant="minimal"
            title="Project Stage"
            subtitle="Active projects by phase"
            height={panelSx.height}
          >
            <ProjectStageChart rows={summary?.projects_by_stage ?? []} />
          </DashboardPanel>
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            variant="minimal"
            title="Project Health"
            subtitle="Portfolio risk distribution"
            height={panelSx.height}
          >
            <ProjectHealthChart
              green={summary?.green_projects ?? 0}
              yellow={summary?.yellow_projects ?? 0}
              red={summary?.red_projects ?? 0}
              grey={greyHealth}
            />
          </DashboardPanel>
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            variant="minimal"
            title="Resource Availability"
            subtitle="Open capacity across the team"
            height={panelSx.height}
          >
            <ResourceAvailabilityPanel
              summary={summary?.designer_availability_summary}
              rows={summary?.designer_availability ?? []}
              limit={4}
            />
          </DashboardPanel>
        )}
      </Grid>
    </Grid>
  );
}
