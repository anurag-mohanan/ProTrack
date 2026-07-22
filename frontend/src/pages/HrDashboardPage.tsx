import {
  Card,
  CardContent,
  Chip,
  Grid,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { apiClient } from '../api/client';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';

type HrUserRow = {
  id: string;
  name: string;
  email: string;
  latest_timesheet_status: string;
  latest_week_start: string | null;
  hours_this_week: number;
  missing_days: number;
  needs_attention: boolean;
};

export function HrDashboardPage() {
  const query = useQuery({
    queryKey: ['hr-dashboard'],
    queryFn: async () => (await apiClient.get('/hr/dashboard')).data,
  });

  if (query.isLoading) return <LoadingState message="Loading HR dashboard…" />;
  const data = query.data;
  const users: HrUserRow[] = data?.users ?? [];
  const attention: HrUserRow[] = data?.timesheet_attention ?? [];

  return (
    <Stack spacing={2}>
      <PageHeader
        title="HR Dashboard"
        subtitle="View assigned teams, monitor timesheet completion, and follow up with people who are behind. Engineering project edit is not included."
      />
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 3 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption">Teams Visible</Typography>
              <Typography variant="h5">{data?.teams_managed ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 3 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption">Team Members</Typography>
              <Typography variant="h5">{data?.team_members ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 3 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption">Pending Timesheets</Typography>
              <Typography variant="h5">{data?.pending_timesheets ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 3 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption">Needs Attention</Typography>
              <Typography variant="h5" color={attention.length ? 'warning.main' : 'text.primary'}>
                {data?.users_needing_attention ?? 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Typography variant="h6">Timesheet completion — follow up</Typography>
      <Typography variant="body2" color="text.secondary">
        Users with missing working days or draft timesheets in your assigned teams. Open{' '}
        <Link component={RouterLink} to="/timesheets">
          Timesheets
        </Link>{' '}
        to review details.
      </Typography>
      <Card variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Hours (week)</TableCell>
              <TableCell align="right">Missing days</TableCell>
              <TableCell>Attention</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(attention.length ? attention : users.slice(0, 25)).map((user) => (
              <TableRow key={user.id}>
                <TableCell>
                  <Typography sx={{ fontWeight: 600 }}>{user.name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {user.email}
                  </Typography>
                </TableCell>
                <TableCell>{user.latest_timesheet_status}</TableCell>
                <TableCell align="right">{user.hours_this_week.toFixed(1)}</TableCell>
                <TableCell align="right">{user.missing_days}</TableCell>
                <TableCell>
                  {user.needs_attention ? (
                    <Chip size="small" color="warning" label="Follow up" />
                  ) : (
                    <Chip size="small" color="success" variant="outlined" label="OK" />
                  )}
                </TableCell>
              </TableRow>
            ))}
            {!users.length ? (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography color="text.secondary">
                    No team members in your assigned teams yet. Ask Admin to assign teams to this HR /
                    Office Admin user.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </Card>

      <Typography variant="h6">Assigned teams</Typography>
      <Stack spacing={1}>
        {(data?.teams ?? []).map((team: { id: string; name: string }) => (
          <Card key={team.id} variant="outlined">
            <CardContent>
              <Typography sx={{ fontWeight: 600 }}>{team.name}</Typography>
            </CardContent>
          </Card>
        ))}
      </Stack>
      <Typography color="text.secondary">
        Leave & attendance remain on GreytHR. New-hire checklists (PP-HRD-FO-14) auto-route owners and
        Help Desk tickets — open{' '}
        <Link component={RouterLink} to="/hr/onboarding">
          Human Resources → Onboarding
        </Link>
        .
      </Typography>
    </Stack>
  );
}

export default HrDashboardPage;
