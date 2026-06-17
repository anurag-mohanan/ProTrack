import { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import PageHeader from '../components/common/PageHeader';
import AlertBanner from '../components/common/AlertBanner';
import StatusChip from '../components/common/StatusChip';
import {
  milestonesApi,
  projectsApi,
  timesheetEntriesApi,
  timesheetsApi,
} from '../api/resources';
import type { Project } from '../types';

export default function ReportsPage() {
  const [error, setError] = useState<string | null>(null);
  const [projectsByStatus, setProjectsByStatus] = useState<Record<string, number>>({});
  const [totalHours, setTotalHours] = useState(0);
  const [timesheetCounts, setTimesheetCounts] = useState<Record<string, number>>({});
  const [overdueMilestones, setOverdueMilestones] = useState(0);
  const [recentProjects, setRecentProjects] = useState<Project[]>([]);

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    Promise.all([
      projectsApi.list(),
      timesheetsApi.list(),
      timesheetEntriesApi.list(),
      milestonesApi.list(),
    ])
      .then(([projects, timesheets, entries, milestones]) => {
        const statusCounts: Record<string, number> = {};
        projects.forEach((p) => {
          statusCounts[p.status] = (statusCounts[p.status] ?? 0) + 1;
        });
        setProjectsByStatus(statusCounts);

        const sheetCounts: Record<string, number> = {};
        timesheets.forEach((t) => {
          sheetCounts[t.status] = (sheetCounts[t.status] ?? 0) + 1;
        });
        setTimesheetCounts(sheetCounts);

        setTotalHours(entries.reduce((sum, e) => sum + Number(e.hours), 0));
        setOverdueMilestones(
          milestones.filter(
            (m) => m.due_date && m.due_date < today && m.status !== 'completed',
          ).length,
        );
        setRecentProjects(projects.slice(0, 5));
      })
      .catch((err) => setError(err.message));
  }, []);

  return (
    <Box>
      <PageHeader
        title="Reports"
        subtitle="Summary reporting across projects, milestones, and timesheets"
      />
      <AlertBanner message={error} onClose={() => setError(null)} />

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Projects by Status</Typography>
              <List dense>
                {Object.entries(projectsByStatus).map(([status, count]) => (
                  <ListItem key={status} secondaryAction={<Typography sx={{ fontWeight: 700 }}>{count}</Typography>}>
                    <ListItemText primary={<StatusChip value={status} />} />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Timesheet Summary</Typography>
              <Typography variant="h3" sx={{ mb: 2 }}>{totalHours.toFixed(1)}h</Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>Total logged hours</Typography>
              <List dense>
                {Object.entries(timesheetCounts).map(([status, count]) => (
                  <ListItem key={status} secondaryAction={<Typography sx={{ fontWeight: 700 }}>{count}</Typography>}>
                    <ListItemText primary={<StatusChip value={status} />} />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Milestone Health</Typography>
              <Typography variant="h3" color="warning.main">{overdueMilestones}</Typography>
              <Typography variant="body2" color="text.secondary">Overdue milestones</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Recent Projects</Typography>
              <List>
                {recentProjects.map((p) => (
                  <ListItem key={p.id} secondaryAction={<StatusChip value={p.status} />}>
                    <ListItemText primary={`${p.code} — ${p.name}`} secondary={p.planned_start ?? 'No start date'} />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
