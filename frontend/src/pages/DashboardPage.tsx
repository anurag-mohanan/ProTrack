import { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import FolderIcon from '@mui/icons-material/Folder';
import EventIcon from '@mui/icons-material/Event';
import WarningIcon from '@mui/icons-material/Warning';
import ScheduleIcon from '@mui/icons-material/Schedule';
import PageHeader from '../components/common/PageHeader';
import AlertBanner from '../components/common/AlertBanner';
import { projectsApi, timesheetEntriesApi } from '../api/resources';

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

function startOfWeek(date: Date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function endOfWeek(date: Date) {
  const start = startOfWeek(date);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  end.setHours(23, 59, 59, 999);
  return end;
}

function parseDate(value: string) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

export default function DashboardPage() {
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    activeProjects: 0,
    dueThisWeek: 0,
    overdueProjects: 0,
    hoursThisMonth: 0,
  });

  useEffect(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const weekStart = startOfWeek(today);
    const weekEnd = endOfWeek(today);
    const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
    const monthEnd = new Date(today.getFullYear(), today.getMonth() + 1, 0, 23, 59, 59, 999);

    Promise.all([projectsApi.list(), timesheetEntriesApi.list()])
      .then(([projects, entries]) => {
        const activeProjects = projects.filter(
          (p) => p.status === 'in_progress' || p.status === 'waiting_for_customer',
        ).length;

        const dueThisWeek = projects.filter((p) => {
          if (p.status === 'completed') return false;
          const due = parseDate(p.due_date);
          return due >= weekStart && due <= weekEnd;
        }).length;

        const overdueProjects = projects.filter((p) => {
          if (p.status === 'completed') return false;
          return parseDate(p.due_date) < today;
        }).length;

        const hoursThisMonth = entries
          .filter((e) => {
            const entryDate = parseDate(e.entry_date);
            return entryDate >= monthStart && entryDate <= monthEnd;
          })
          .reduce((sum, e) => sum + e.hours, 0);

        setStats({
          activeProjects,
          dueThisWeek,
          overdueProjects,
          hoursThisMonth: Math.round(hoursThisMonth * 10) / 10,
        });
      })
      .catch((err) => setError(err.message));
  }, []);

  return (
    <Box>
      <PageHeader title="Dashboard" subtitle="Overview of projects and timesheets" />
      <AlertBanner message={error} onClose={() => setError(null)} />
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Active Projects" value={stats.activeProjects} icon={<FolderIcon />} accent="primary" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Due This Week" value={stats.dueThisWeek} icon={<EventIcon />} accent="info" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Overdue Projects" value={stats.overdueProjects} icon={<WarningIcon />} accent="warning" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Hours This Month" value={stats.hoursThisMonth} icon={<ScheduleIcon />} accent="success" />
        </Grid>
      </Grid>
    </Box>
  );
}
