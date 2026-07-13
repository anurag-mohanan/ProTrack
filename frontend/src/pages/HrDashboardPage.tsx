import { Card, CardContent, Grid, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';

export function HrDashboardPage() {
  const query = useQuery({
    queryKey: ['hr-dashboard'],
    queryFn: async () => (await api.get('/hr/dashboard')).data,
  });

  if (query.isLoading) return <LoadingState message="Loading HR dashboard…" />;
  const data = query.data;

  return (
    <Stack spacing={2}>
      <PageHeader
        title="Human Resources"
        subtitle="Team visibility, timesheet completion, and productivity (read-only). Attendance and onboarding are future modules."
      />
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption">Teams Managed</Typography>
              <Typography variant="h5">{data?.teams_managed ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption">Team Members</Typography>
              <Typography variant="h5">{data?.team_members ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption">Pending Timesheets</Typography>
              <Typography variant="h5">{data?.pending_timesheets ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
      <Typography color="text.secondary">{data?.leave_placeholder}</Typography>
      <Typography color="text.secondary">{data?.onboarding_placeholder}</Typography>
      <Typography variant="h6">Assigned teams</Typography>
      <Stack spacing={1}>
        {(data?.teams ?? []).map((team: { id: string; name: string }) => (
          <Card key={team.id} variant="outlined">
            <CardContent>
              <Typography fontWeight={600}>{team.name}</Typography>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </Stack>
  );
}

export default HrDashboardPage;
