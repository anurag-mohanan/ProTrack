import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Chip,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { aiQueryKeys, fetchExecutiveWall } from '../api/ai';
import { fetchResourcePlanningGrid, resourcePlanningQueryKeys } from '../api/resourcePlanning';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { designTokens } from '../theme/designTokens';
import type { WallProjectCard, WallTeamLiveBlock } from '../types/Ai';
import { formatDate, formatDisplayValue, formatNumber } from '../utils/format';

function healthColor(health?: string | null): string {
  if (health === 'red') return designTokens.semantic.danger;
  if (health === 'yellow') return designTokens.semantic.warning;
  return designTokens.semantic.success;
}

function DeliveryTable({
  rows,
  emptyLabel,
}: {
  rows: WallProjectCard[];
  emptyLabel: string;
}) {
  if (!rows.length) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 1.5 }}>
        {emptyLabel}
      </Typography>
    );
  }

  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>Tool</TableCell>
          <TableCell>Customer</TableCell>
          <TableCell>Team</TableCell>
          <TableCell>Designer</TableCell>
          <TableCell>Due</TableCell>
          <TableCell>Health</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={`${row.tool_number}-${row.due_date ?? ''}-${row.project_id ?? ''}`} hover>
            <TableCell sx={{ fontWeight: 700 }}>{row.tool_number}</TableCell>
            <TableCell>{formatDisplayValue(row.customer_name)}</TableCell>
            <TableCell>{formatDisplayValue(row.team_name)}</TableCell>
            <TableCell>{formatDisplayValue(row.designer_name)}</TableCell>
            <TableCell sx={{ whiteSpace: 'nowrap' }}>
              {row.due_date ? formatDate(row.due_date) : '—'}
            </TableCell>
            <TableCell>
              <Chip
                size="small"
                label={(row.health ?? 'green').toUpperCase()}
                sx={{
                  bgcolor: `${healthColor(row.health)}22`,
                  color: healthColor(row.health),
                  fontWeight: 700,
                }}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function TeamLiveProjects({ teams }: { teams: WallTeamLiveBlock[] }) {
  if (!teams.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No live projects on the board right now.
      </Typography>
    );
  }

  return (
    <Stack spacing={1}>
      {teams.map((team) => (
        <Accordion
          key={`${team.team_id ?? 'none'}-${team.team_name}`}
          defaultExpanded={team.red_count > 0 || team.active_count <= 6}
          disableGutters
          elevation={0}
          sx={{
            border: 1,
            borderColor: 'divider',
            borderRadius: '8px !important',
            '&:before': { display: 'none' },
          }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack
              direction="row"
              spacing={1}
              useFlexGap
              sx={{ width: '100%', pr: 1, alignItems: 'center', flexWrap: 'wrap' }}
            >
              <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                {team.team_name}
              </Typography>
              <Chip size="small" label={`${team.active_count} live`} color="primary" variant="outlined" />
              {team.red_count > 0 ? (
                <Chip size="small" color="error" label={`${team.red_count} red`} />
              ) : null}
              {team.yellow_count > 0 ? (
                <Chip size="small" color="warning" label={`${team.yellow_count} yellow`} />
              ) : null}
            </Stack>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Tool</TableCell>
                  <TableCell>Customer</TableCell>
                  <TableCell>Designer</TableCell>
                  <TableCell>Stage / Milestone</TableCell>
                  <TableCell>Due</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Health</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {team.projects.map((project) => (
                  <TableRow key={project.project_id ?? project.tool_number} hover>
                    <TableCell sx={{ fontWeight: 700 }}>{project.tool_number}</TableCell>
                    <TableCell>{formatDisplayValue(project.customer_name)}</TableCell>
                    <TableCell>{formatDisplayValue(project.designer_name)}</TableCell>
                    <TableCell>
                      {formatDisplayValue(project.current_milestone || project.project_stage)}
                    </TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>
                      {project.due_date ? formatDate(project.due_date) : '—'}
                    </TableCell>
                    <TableCell>{formatDisplayValue(project.execution_status)}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={(project.health ?? 'green').toUpperCase()}
                        sx={{
                          bgcolor: `${healthColor(project.health)}22`,
                          color: healthColor(project.health),
                          fontWeight: 700,
                        }}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AccordionDetails>
        </Accordion>
      ))}
    </Stack>
  );
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        height: '100%',
      }}
    >
      <Typography variant="h6" sx={{ fontWeight: 800 }}>
        {title}
      </Typography>
      {subtitle ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.25 }}>
          {subtitle}
        </Typography>
      ) : (
        <Box sx={{ mb: 1 }} />
      )}
      {children}
    </Box>
  );
}

export default function PlanningBoardPage() {
  const wallQuery = useQuery({
    queryKey: aiQueryKeys.executiveWall,
    queryFn: fetchExecutiveWall,
    refetchInterval: 60_000,
  });

  const gridQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.grid({ granularity: 'week' }),
    queryFn: () => fetchResourcePlanningGrid({ granularity: 'week' }),
    refetchInterval: 60_000,
  });

  if (wallQuery.isLoading) return <LoadingState message="Loading planning board…" />;
  if (wallQuery.error) {
    return <ErrorState error={wallQuery.error} title="Unable to load planning board" />;
  }

  const data = wallQuery.data!;
  const teamsLive = data.teams_live ?? [];
  const upcoming = data.upcoming_deliveries ?? [];
  const late = data.late_deliveries ?? [];
  const designers = gridQuery.data?.designers ?? [];
  const overloaded = designers.filter(
    (row) => Number(row.capacity_hours || 0) > 0 && Number(row.allocated_hours || 0) >= Number(row.capacity_hours),
  ).length;
  const refreshed = data.refreshed_at
    ? new Date(data.refreshed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '—';

  return (
    <Stack spacing={2.25}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1}
        sx={{ justifyContent: 'space-between', alignItems: { md: 'center' } }}
      >
        <Box>
          <Typography variant="body2" color="text.secondary">
            Read-only operations monitor · refreshes every 60 seconds · no edit controls
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Layout: KPIs → Deliveries → Team-wise live projects → Capacity & releases
          </Typography>
        </Box>
        <Chip size="small" variant="outlined" label={`Last refresh ${refreshed}`} />
      </Stack>

      <Grid container spacing={2}>
        {[
          { label: 'Active Projects', value: data.active_projects },
          { label: 'Utilization', value: `${data.utilization_percent}%` },
          { label: 'Late Milestones', value: data.late_milestones, warn: data.late_milestones > 0 },
          { label: 'Hours This Month', value: formatNumber(data.hours_logged_month, 0) },
          { label: 'Team Capacity', value: formatNumber(data.capacity_hours, 0) },
          {
            label: 'Health (G/Y/R)',
            value: `${data.health_summary.green ?? 0}/${data.health_summary.yellow ?? 0}/${data.health_summary.red ?? 0}`,
          },
        ].map((stat) => (
          <Grid key={stat.label} size={{ xs: 6, md: 4, lg: 2 }}>
            <Box
              sx={{
                p: 2,
                borderRadius: 2,
                border: 1,
                borderColor: 'divider',
                bgcolor: 'background.paper',
              }}
            >
              <Typography
                variant="h4"
                sx={{
                  fontWeight: 800,
                  color: stat.warn ? designTokens.semantic.warning : 'text.primary',
                }}
              >
                {stat.value}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {stat.label}
              </Typography>
            </Box>
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 6 }}>
          <Panel
            title="Deliveries coming up"
            subtitle="Due within the next 7 days — chase owners before slip"
          >
            <DeliveryTable rows={upcoming} emptyLabel="No upcoming deliveries in the next 7 days." />
          </Panel>
        </Grid>
        <Grid size={{ xs: 12, lg: 6 }}>
          <Panel
            title="Late deliveries"
            subtitle="Past due — Program Manager follow-up board"
          >
            <DeliveryTable
              rows={late}
              emptyLabel="No late deliveries. Keep watching due dates as work progresses."
            />
          </Panel>
        </Grid>
      </Grid>

      <Panel
        title="Team-wise live projects"
        subtitle="Active and on-hold tools grouped by delivery team (red / yellow first)"
      >
        <TeamLiveProjects teams={teamsLive} />
      </Panel>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Panel title="Capacity snapshot" subtitle="This week — read only">
            {gridQuery.isLoading ? (
              <Typography variant="body2" color="text.secondary">
                Loading capacity…
              </Typography>
            ) : gridQuery.error ? (
              <Typography variant="body2" color="text.secondary">
                Capacity grid unavailable
              </Typography>
            ) : (
              <Stack spacing={0.75}>
                <Typography variant="body2">
                  Designers on board: <strong>{designers.length}</strong>
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ color: overloaded > 0 ? designTokens.semantic.warning : 'text.primary' }}
                >
                  At or over capacity: <strong>{overloaded}</strong>
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Assignments cannot be changed from this monitor account.
                </Typography>
              </Stack>
            )}
          </Panel>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Panel title="Recent releases" subtitle="Completed in the last 30 days">
            <Stack spacing={0.75}>
              {(data.recent_releases ?? []).length ? (
                data.recent_releases.map((row, index) => (
                  <Typography key={index} variant="body2">
                    {String(row.tool_number ?? '—')}
                    {row.completed_at ? ` · ${String(row.completed_at)}` : ''}
                  </Typography>
                ))
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No releases in the last 30 days
                </Typography>
              )}
            </Stack>
          </Panel>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Panel title="Customer load" subtitle="Share of active engineering work">
            <Stack spacing={0.75}>
              {(data.customer_distribution ?? []).length ? (
                data.customer_distribution.map((row, index) => (
                  <Typography key={index} variant="body2">
                    {String(row.customer_name ?? row.name ?? 'Customer')}:{' '}
                    <strong>{String(row.percent ?? row.share ?? row.hours ?? '—')}</strong>
                  </Typography>
                ))
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No customer distribution available
                </Typography>
              )}
            </Stack>
          </Panel>
        </Grid>
      </Grid>
    </Stack>
  );
}
