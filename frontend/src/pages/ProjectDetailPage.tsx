import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { fetchProjectDashboard } from '../api/dashboard';
import { fetchCustomers, fetchUsers } from '../api/lookups';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { HealthChip, StatusChip } from '../components/common/StatusChip';
import { LoadingState } from '../components/common/LoadingState';
import { ProjectMilestonesTab } from '../components/projects/ProjectMilestonesTab';
import { ProjectTimesheetsTab } from '../components/projects/ProjectTimesheetsTab';
import { formatDate, formatNumber, userDisplayName } from '../utils/format';

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 1, gap: 2 }}>
      <Typography color="text.secondary">{label}</Typography>
      <Typography sx={{ fontWeight: 600, textAlign: 'right' }}>
        {value}
      </Typography>
    </Box>
  );
}

export function ProjectDetailPage() {
  const { id = '' } = useParams();
  const [tab, setTab] = useState(0);

  const dashboardQuery = useQuery({
    queryKey: ['dashboard', 'project', id],
    queryFn: () => fetchProjectDashboard(id),
    enabled: Boolean(id),
  });

  const customersQuery = useQuery({
    queryKey: ['customers'],
    queryFn: fetchCustomers,
  });

  const usersQuery = useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers,
  });

  if (dashboardQuery.isLoading) return <LoadingState />;
  if (dashboardQuery.error) return <ErrorState error={dashboardQuery.error} />;
  if (!dashboardQuery.data) return <EmptyState title="Project not found" />;

  const { project, milestone_summary, hours } = dashboardQuery.data;
  const customerName =
    customersQuery.data?.find((customer) => customer.id === project.customer_id)?.name ??
    '—';
  const designLeader =
    usersQuery.data?.find((user) => user.id === project.design_leader_id);
  const designer = project.designer_id
    ? usersQuery.data?.find((user) => user.id === project.designer_id)
    : undefined;

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }} gutterBottom>
        {project.tool_number}
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        {project.part_description}
      </Typography>

      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 3 }}>
        <Tab label="Overview" />
        <Tab label="Milestones" />
        <Tab label="Timesheets" />
      </Tabs>

      {tab === 0 && (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Project Information
                </Typography>
                <InfoRow label="Code" value={project.code} />
                <InfoRow label="Customer" value={customerName} />
                <InfoRow label="Due Date" value={formatDate(project.due_date)} />
                <InfoRow
                  label="Design Leader"
                  value={designLeader ? userDisplayName(designLeader) : '—'}
                />
                <InfoRow
                  label="Designer"
                  value={designer ? userDisplayName(designer) : '—'}
                />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 1 }}>
                  <Typography color="text.secondary">Status</Typography>
                  <StatusChip status={project.status} />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 1 }}>
                  <Typography color="text.secondary">Health</Typography>
                  <HealthChip health={project.health} />
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 3 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Milestone Summary
                </Typography>
                <InfoRow
                  label="Completed"
                  value={formatNumber(milestone_summary.completed, 0)}
                />
                <InfoRow
                  label="Remaining"
                  value={formatNumber(milestone_summary.remaining, 0)}
                />
                <InfoRow
                  label="Progress"
                  value={`${formatNumber(milestone_summary.progress_percent)}%`}
                />
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 3 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Hours Summary
                </Typography>
                <InfoRow label="Quoted" value={formatNumber(hours.quoted)} />
                <InfoRow label="Actual" value={formatNumber(hours.actual)} />
                <InfoRow label="Variance" value={formatNumber(hours.variance)} />
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {tab === 1 && <ProjectMilestonesTab projectId={project.id} />}

      {tab === 2 && (
        <ProjectTimesheetsTab entries={dashboardQuery.data.recent_timesheet_entries} />
      )}

      <Box sx={{ mt: 3 }}>
        <Link to="/projects">← Back to projects</Link>
      </Box>
    </Box>
  );
}
