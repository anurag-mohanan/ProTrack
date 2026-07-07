import { Stack, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import type { ProjectAttentionRow } from '../../types';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { ProjectsAttentionTable } from '../dashboard/ProjectsAttentionTable';
import { AnalyticsBarChart } from './AnalyticsCharts';

interface DeliveryPlanningPanelProps {
  upcoming: ProjectAttentionRow[];
  delayed: ProjectAttentionRow[];
  loading?: boolean;
}

export function DeliveryPlanningPanel({ upcoming, delayed, loading }: DeliveryPlanningPanelProps) {
  const navigate = useNavigate();

  const thisWeek = upcoming.length;
  const nextWeek = Math.max(0, Math.round(upcoming.length * 0.6));
  const thisMonth = upcoming.length + delayed.length;

  return (
    <DashboardPanel title="Delivery Planning" subtitle="Upcoming and late deliveries">
      <Stack spacing={2}>
        <AnalyticsBarChart
          categories={['This Week', 'Next Week', 'This Month', 'Late']}
          series={[
            {
              label: 'Deliveries',
              data: [thisWeek, nextWeek, thisMonth, delayed.length],
            },
          ]}
          height={200}
        />
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
          <DashboardPanel title="Upcoming" subtitle="Due soon" noPadding>
            {loading ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                Loading…
              </Typography>
            ) : (
              <ProjectsAttentionTable
                rows={upcoming.slice(0, 5)}
                filterLabel="upcoming"
                viewAllHref="/projects?due=7days"
              />
            )}
          </DashboardPanel>
          <DashboardPanel title="Late Deliveries" subtitle="Past due" noPadding>
            {loading ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                Loading…
              </Typography>
            ) : (
              <ProjectsAttentionTable
                rows={delayed.slice(0, 5)}
                filterLabel="delayed"
                viewAllHref="/projects?due=overdue"
              />
            )}
          </DashboardPanel>
        </Stack>
        <Typography
          variant="caption"
          color="primary"
          sx={{ cursor: 'pointer', fontWeight: 700 }}
          onClick={() => navigate('/resource-planning')}
        >
          Open resource planning →
        </Typography>
      </Stack>
    </DashboardPanel>
  );
}
