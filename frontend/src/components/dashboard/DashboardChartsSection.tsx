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

  return (
    <Grid container spacing={2} sx={{ mt: 0.5 }}>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            title="Customer Workload"
            subtitle="Top customers by hours logged"
            height={320}
          >
            <CustomerWorkloadChart rows={summary?.customer_workload ?? []} height={220} />
          </DashboardPanel>
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            title="Designer Utilization"
            subtitle="Current loading by assignment status"
            height={320}
          >
            <DesignerUtilizationList rows={summary?.designer_availability ?? []} limit={6} />
          </DashboardPanel>
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            title="Hours Burn"
            subtitle="Billable, non-billable, and NP hours"
            height={320}
          >
            <HoursSummaryChart
              billableHours={summary?.billable_hours ?? 0}
              nonBillableHours={summary?.non_billable_hours ?? 0}
              npHours={summary?.np_hours ?? 0}
              height={220}
            />
          </DashboardPanel>
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            title="Project Stage Distribution"
            subtitle="Active projects by phase"
            height={320}
          >
            <ProjectStageChart rows={summary?.projects_by_stage ?? []} height={220} />
          </DashboardPanel>
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            title="Project Health"
            subtitle="Portfolio risk distribution"
            height={320}
          >
            <ProjectHealthChart
              green={summary?.green_projects ?? 0}
              yellow={summary?.yellow_projects ?? 0}
              red={summary?.red_projects ?? 0}
              grey={greyHealth}
              height={220}
            />
          </DashboardPanel>
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6, xl: 4 }}>
        {loading ? (
          <DashboardPanelSkeleton height={280} />
        ) : (
          <DashboardPanel
            title="Resource Availability"
            subtitle="Designers with open capacity"
            height={320}
          >
            <ResourceAvailabilityPanel
              summary={summary?.designer_availability_summary}
              rows={summary?.designer_availability ?? []}
              limit={5}
            />
          </DashboardPanel>
        )}
      </Grid>
    </Grid>
  );
}
