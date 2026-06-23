import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Grid,
  LinearProgress,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { fetchCustomers, fetchStreams, fetchUsers } from '../api/lookups';
import { ProjectFormDialog } from '../components/projects/ProjectFormDialog';
import { ProjectMilestonesTab } from '../components/projects/ProjectMilestonesTab';
import { ProjectTimesheetsTab } from '../components/projects/ProjectTimesheetsTab';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { HealthChip, StatusChip } from '../components/common/StatusChip';
import { LoadingState } from '../components/common/LoadingState';
import { getProjectDetail, projectQueryKeys } from '../services/projectService';
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
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(0);
  const [editOpen, setEditOpen] = useState(false);

  const detailQuery = useQuery({
    queryKey: projectQueryKeys.detail(id),
    queryFn: () => getProjectDetail(id),
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

  const streamsQuery = useQuery({
    queryKey: ['streams'],
    queryFn: fetchStreams,
  });

  if (detailQuery.isLoading) return <LoadingState message="Loading project…" />;
  if (detailQuery.error) return <ErrorState error={detailQuery.error} />;
  if (!detailQuery.data) return <EmptyState title="Project not found" />;

  const { project, milestone_summary, hours, health } = detailQuery.data;
  const customerName =
    customersQuery.data?.find((customer) => customer.id === project.customer_id)?.name ??
    '—';
  const streamName =
    streamsQuery.data?.find((stream) => stream.id === project.stream_id)?.name ?? '—';
  const designLeader =
    usersQuery.data?.find((user) => user.id === project.design_leader_id);
  const designer = project.designer_id
    ? usersQuery.data?.find((user) => user.id === project.designer_id)
    : undefined;
  const surfacer = project.surfacer_id
    ? usersQuery.data?.find((user) => user.id === project.surfacer_id)
    : undefined;

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 2,
          mb: 3,
          flexWrap: 'wrap',
        }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }} gutterBottom>
            {project.tool_number}
          </Typography>
          <Typography color="text.secondary">{project.part_description}</Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<EditIcon />}
          onClick={() => setEditOpen(true)}
        >
          Edit Project
        </Button>
      </Box>

      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 3 }}>
        <Tab label="Overview" />
        <Tab label="Milestones" />
        <Tab label="Timesheets" />
      </Tabs>

      {tab === 0 && (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, lg: 6 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Project Information
                </Typography>
                <InfoRow label="Code" value={project.code} />
                <InfoRow label="Customer" value={customerName} />
                <InfoRow label="Stream" value={streamName} />
                <InfoRow label="Due Date" value={formatDate(project.due_date)} />
                <InfoRow
                  label="Design Leader"
                  value={designLeader ? userDisplayName(designLeader) : '—'}
                />
                <InfoRow
                  label="Designer"
                  value={designer ? userDisplayName(designer) : '—'}
                />
                <InfoRow
                  label="Surfacer"
                  value={surfacer ? userDisplayName(surfacer) : '—'}
                />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 1 }}>
                  <Typography color="text.secondary">Status</Typography>
                  <StatusChip status={project.status} />
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, lg: 2 }}>
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
                  label="Milestone Progress"
                  value={`${formatNumber(milestone_summary.progress_percent)}%`}
                />
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, lg: 2 }}>
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

          <Grid size={{ xs: 12, sm: 6, lg: 2 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Health & Progress
                </Typography>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 1 }}>
                  <Typography color="text.secondary">Health</Typography>
                  <HealthChip health={health} />
                </Box>
                <InfoRow
                  label="Progress"
                  value={`${formatNumber(milestone_summary.progress_percent)}%`}
                />
                <LinearProgress
                  variant="determinate"
                  value={Math.min(Number(milestone_summary.progress_percent), 100)}
                  sx={{ mt: 2, height: 8, borderRadius: 1 }}
                />
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {tab === 1 && <ProjectMilestonesTab projectId={project.id} />}

      {tab === 2 && (
        <ProjectTimesheetsTab entries={detailQuery.data.recent_timesheet_entries} />
      )}

      <Box sx={{ mt: 3 }}>
        <Link to="/projects">← Back to projects</Link>
      </Box>

      <ProjectFormDialog
        open={editOpen}
        onClose={() => setEditOpen(false)}
        project={project}
        onUpdated={() => {
          void queryClient.invalidateQueries({ queryKey: projectQueryKeys.detail(id) });
        }}
      />
    </Box>
  );
}
