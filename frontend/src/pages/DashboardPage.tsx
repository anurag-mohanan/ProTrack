import { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import FolderIcon from '@mui/icons-material/Folder';
import FlagIcon from '@mui/icons-material/Flag';
import ScheduleIcon from '@mui/icons-material/Schedule';
import GroupsIcon from '@mui/icons-material/Groups';
import PageHeader from '../components/common/PageHeader';
import AlertBanner from '../components/common/AlertBanner';
import {
  milestonesApi,
  projectMembersApi,
  projectsApi,
  timesheetsApi,
} from '../api/resources';

interface StatCardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
  accent: 'primary' | 'success' | 'warning' | 'info' | 'secondary';
}

function StatCard({ label, value, icon, accent }: StatCardProps) {
  return (
    <Card>
      <CardContent>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="overline" color="text.secondary">
              {label}
            </Typography>
            <Typography variant="h3">{value}</Typography>
          </Box>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: 2,
              bgcolor: `${accent}.light`,
              color: `${accent}.dark`,
              display: 'grid',
              placeItems: 'center',
            }}
          >
            {icon}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    projects: 0,
    activeProjects: 0,
    pendingMilestones: 0,
    submittedTimesheets: 0,
    allocations: 0,
  });

  useEffect(() => {
    Promise.all([
      projectsApi.list(),
      milestonesApi.list(),
      timesheetsApi.list(),
      projectMembersApi.list(),
    ])
      .then(([projects, milestones, timesheets, members]) => {
        setStats({
          projects: projects.length,
          activeProjects: projects.filter((p) => p.status === 'active').length,
          pendingMilestones: milestones.filter((m) => m.status === 'pending').length,
          submittedTimesheets: timesheets.filter((t) => t.status === 'submitted').length,
          allocations: members.length,
        });
      })
      .catch((err) => setError(err.message));
  }, []);

  return (
    <Box>
      <PageHeader
        title="Dashboard"
        subtitle="Overview of projects, milestones, timesheets, and resource planning"
      />
      <AlertBanner message={error} onClose={() => setError(null)} />
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Total Projects" value={stats.projects} icon={<FolderIcon />} accent="primary" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Active Projects" value={stats.activeProjects} icon={<FolderIcon />} accent="success" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Pending Milestones" value={stats.pendingMilestones} icon={<FlagIcon />} accent="warning" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Timesheets to Approve" value={stats.submittedTimesheets} icon={<ScheduleIcon />} accent="info" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Resource Allocations" value={stats.allocations} icon={<GroupsIcon />} accent="secondary" />
        </Grid>
      </Grid>
    </Box>
  );
}
