import { Box, Chip, Grid, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { keyframes } from '@mui/system';
import { aiQueryKeys, fetchExecutiveWall } from '../api/ai';
import { fetchResourcePlanningGrid, resourcePlanningQueryKeys } from '../api/resourcePlanning';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { designTokens } from '../theme/designTokens';
import type { WallProjectCard, WallTeamLiveBlock } from '../types/Ai';
import { formatDate, formatDisplayValue, formatNumber } from '../utils/format';

const fadeUp = keyframes`
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
`;

const WALL = {
  panel: 'rgba(30, 41, 59, 0.92)',
  panelBorder: 'rgba(148, 163, 184, 0.22)',
  text: '#f8fafc',
  muted: 'rgba(203, 213, 225, 0.88)',
  soft: 'rgba(148, 163, 184, 0.16)',
} as const;

function healthTone(health?: string | null) {
  if (health === 'red') return designTokens.health.red;
  if (health === 'yellow') return designTokens.health.yellow;
  return designTokens.health.green;
}

function WallPanel({
  title,
  subtitle,
  accent,
  children,
  delayMs = 0,
}: {
  title: string;
  subtitle?: string;
  accent?: string;
  children: ReactNode;
  delayMs?: number;
}) {
  return (
    <Box
      sx={{
        height: '100%',
        p: { xs: 2, md: 2.5 },
        borderRadius: 3,
        bgcolor: WALL.panel,
        border: `1px solid ${WALL.panelBorder}`,
        borderTop: accent ? `4px solid ${accent}` : undefined,
        boxShadow: '0 10px 30px rgba(2, 6, 23, 0.28)',
        animation: `${fadeUp} 0.45s ease both`,
        animationDelay: `${delayMs}ms`,
      }}
    >
      <Typography
        sx={{
          fontWeight: 800,
          fontSize: { xs: '1.15rem', md: '1.35rem' },
          color: WALL.text,
          letterSpacing: '-0.02em',
        }}
      >
        {title}
      </Typography>
      {subtitle ? (
        <Typography sx={{ color: WALL.muted, mb: 1.75, mt: 0.35, fontSize: '0.95rem', fontWeight: 500 }}>
          {subtitle}
        </Typography>
      ) : (
        <Box sx={{ mb: 1.5 }} />
      )}
      {children}
    </Box>
  );
}

function KpiTile({
  label,
  value,
  warn,
  delayMs,
}: {
  label: string;
  value: string | number;
  warn?: boolean;
  delayMs: number;
}) {
  return (
    <Box
      sx={{
        p: { xs: 2, md: 2.25 },
        borderRadius: 3,
        bgcolor: WALL.panel,
        border: `1px solid ${WALL.panelBorder}`,
        borderLeft: `5px solid ${warn ? designTokens.semantic.warning : designTokens.semantic.primary}`,
        minHeight: { xs: 110, md: 132 },
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        animation: `${fadeUp} 0.4s ease both`,
        animationDelay: `${delayMs}ms`,
      }}
    >
      <Typography
        sx={{
          fontWeight: 800,
          fontSize: { xs: '2rem', md: '2.6rem', xl: '3rem' },
          lineHeight: 1,
          color: warn ? '#fbbf24' : WALL.text,
          letterSpacing: '-0.03em',
        }}
      >
        {value}
      </Typography>
      <Typography
        sx={{
          mt: 1,
          color: WALL.muted,
          fontWeight: 700,
          fontSize: { xs: '0.8rem', md: '0.95rem' },
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        {label}
      </Typography>
    </Box>
  );
}

function DeliveryRows({
  rows,
  emptyLabel,
  tone,
}: {
  rows: WallProjectCard[];
  emptyLabel: string;
  tone: 'ok' | 'danger';
}) {
  if (!rows.length) {
    return (
      <Box
        sx={{
          py: 4,
          px: 2,
          borderRadius: 2,
          bgcolor: WALL.soft,
          textAlign: 'center',
        }}
      >
        <Typography sx={{ color: WALL.muted, fontSize: '1.05rem', fontWeight: 600 }}>{emptyLabel}</Typography>
      </Box>
    );
  }

  return (
    <Stack spacing={1.25}>
      {rows.slice(0, 8).map((row) => {
        const health = healthTone(row.health);
        return (
          <Box
            key={`${row.tool_number}-${row.due_date ?? ''}-${row.project_id ?? ''}`}
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '88px 1fr',
                md: '110px minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr) 100px 88px',
              },
              gap: { xs: 1, md: 1.5 },
              alignItems: 'center',
              px: 1.75,
              py: 1.5,
              borderRadius: 2,
              bgcolor: tone === 'danger' ? 'rgba(220, 38, 38, 0.12)' : 'rgba(37, 99, 235, 0.10)',
              border: `1px solid ${
                tone === 'danger' ? 'rgba(248, 113, 113, 0.28)' : 'rgba(96, 165, 250, 0.28)'
              }`,
            }}
          >
            <Typography sx={{ fontWeight: 800, fontSize: '1.2rem', color: WALL.text }}>
              {row.tool_number}
            </Typography>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontWeight: 700, color: WALL.text, fontSize: '1.05rem' }} noWrap>
                {formatDisplayValue(row.customer_name)}
              </Typography>
              <Typography sx={{ color: WALL.muted, fontSize: '0.9rem' }} noWrap>
                {formatDisplayValue(row.team_name)} · {formatDisplayValue(row.designer_name)}
              </Typography>
            </Box>
            <Typography
              sx={{
                display: { xs: 'none', md: 'block' },
                color: WALL.muted,
                fontWeight: 600,
                fontSize: '1rem',
              }}
              noWrap
            >
              {formatDisplayValue(row.current_milestone || row.project_stage)}
            </Typography>
            <Typography
              sx={{
                display: { xs: 'none', md: 'block' },
                color: WALL.text,
                fontWeight: 700,
                fontSize: '1.05rem',
              }}
            >
              {row.due_date ? formatDate(row.due_date) : '—'}
            </Typography>
            <Chip
              label={(row.health ?? 'green').toUpperCase()}
              sx={{
                justifySelf: { xs: 'start', md: 'end' },
                fontWeight: 800,
                bgcolor: health.soft,
                color: health.main,
                height: 32,
                fontSize: '0.8rem',
              }}
            />
          </Box>
        );
      })}
    </Stack>
  );
}

function TeamLiveWall({ teams }: { teams: WallTeamLiveBlock[] }) {
  if (!teams.length) {
    return (
      <Typography sx={{ color: WALL.muted, fontSize: '1.05rem' }}>
        No live projects on the board right now.
      </Typography>
    );
  }

  return (
    <Grid container spacing={2}>
      {teams.map((team, index) => (
        <Grid key={`${team.team_id ?? 'none'}-${team.team_name}`} size={{ xs: 12, xl: 6 }}>
          <Box
            sx={{
              p: 2,
              borderRadius: 2.5,
              bgcolor: 'rgba(15, 23, 42, 0.55)',
              border: `1px solid ${WALL.panelBorder}`,
              animation: `${fadeUp} 0.45s ease both`,
              animationDelay: `${120 + index * 40}ms`,
            }}
          >
            <Stack
              direction="row"
              spacing={1}
              useFlexGap
              sx={{ mb: 1.5, alignItems: 'center', flexWrap: 'wrap' }}
            >
              <Typography sx={{ fontWeight: 800, fontSize: '1.25rem', color: WALL.text, mr: 0.5 }}>
                {team.team_name}
              </Typography>
              <Chip
                label={`${team.active_count} live`}
                sx={{
                  fontWeight: 800,
                  bgcolor: 'rgba(37, 99, 235, 0.22)',
                  color: '#93c5fd',
                }}
              />
              {team.red_count > 0 ? (
                <Chip
                  label={`${team.red_count} red`}
                  sx={{ fontWeight: 800, bgcolor: designTokens.health.red.soft, color: designTokens.health.red.main }}
                />
              ) : null}
              {team.yellow_count > 0 ? (
                <Chip
                  label={`${team.yellow_count} yellow`}
                  sx={{
                    fontWeight: 800,
                    bgcolor: designTokens.health.yellow.soft,
                    color: designTokens.health.yellow.main,
                  }}
                />
              ) : null}
            </Stack>

            <Stack spacing={1}>
              {team.projects.slice(0, 8).map((project) => {
                const health = healthTone(project.health);
                return (
                  <Box
                    key={project.project_id ?? project.tool_number}
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: {
                        xs: '76px 1fr auto',
                        md: '96px minmax(0, 1.3fr) minmax(0, 1fr) 96px 78px',
                      },
                      gap: 1.25,
                      alignItems: 'center',
                      px: 1.5,
                      py: 1.15,
                      borderRadius: 2,
                      bgcolor: WALL.soft,
                      borderLeft: `4px solid ${health.main}`,
                    }}
                  >
                    <Typography sx={{ fontWeight: 800, color: WALL.text, fontSize: '1.1rem' }}>
                      {project.tool_number}
                    </Typography>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography sx={{ fontWeight: 700, color: WALL.text }} noWrap>
                        {formatDisplayValue(project.customer_name)}
                      </Typography>
                      <Typography sx={{ color: WALL.muted, fontSize: '0.88rem' }} noWrap>
                        {formatDisplayValue(project.designer_name)}
                      </Typography>
                    </Box>
                    <Typography
                      sx={{ display: { xs: 'none', md: 'block' }, color: WALL.muted, fontWeight: 600 }}
                      noWrap
                    >
                      {formatDisplayValue(project.current_milestone || project.project_stage)}
                    </Typography>
                    <Typography
                      sx={{
                        display: { xs: 'none', md: 'block' },
                        color: WALL.text,
                        fontWeight: 700,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {project.due_date ? formatDate(project.due_date) : '—'}
                    </Typography>
                    <Chip
                      size="small"
                      label={(project.health ?? 'green').toUpperCase()}
                      sx={{ fontWeight: 800, bgcolor: health.soft, color: health.main }}
                    />
                  </Box>
                );
              })}
            </Stack>
          </Box>
        </Grid>
      ))}
    </Grid>
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

  if (wallQuery.isLoading) {
    return (
      <Box sx={{ color: WALL.text }}>
        <LoadingState message="Loading planning board…" />
      </Box>
    );
  }
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
    <Stack spacing={{ xs: 2, md: 2.75 }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1}
        sx={{ justifyContent: 'space-between', alignItems: { md: 'center' } }}
      >
        <Box>
          <Typography sx={{ color: WALL.text, fontWeight: 800, fontSize: { xs: '1.1rem', md: '1.25rem' } }}>
            Engineering floor — operations pulse
          </Typography>
          <Typography sx={{ color: WALL.muted, fontWeight: 500 }}>
            Auto-refresh every 60s · read-only wall display · no edit controls
          </Typography>
        </Box>
        <Chip
          label={`Synced ${refreshed}`}
          sx={{
            alignSelf: { xs: 'flex-start', md: 'center' },
            fontWeight: 700,
            bgcolor: WALL.soft,
            color: WALL.muted,
            border: `1px solid ${WALL.panelBorder}`,
          }}
        />
      </Stack>

      <Grid container spacing={2}>
        {[
          { label: 'Active Projects', value: data.active_projects },
          { label: 'Utilization', value: `${data.utilization_percent}%` },
          { label: 'Late Milestones', value: data.late_milestones, warn: data.late_milestones > 0 },
          { label: 'Hours This Month', value: formatNumber(data.hours_logged_month, 0) },
          { label: 'Team Capacity', value: formatNumber(data.capacity_hours, 0) },
          {
            label: 'Health G / Y / R',
            value: `${data.health_summary.green ?? 0} / ${data.health_summary.yellow ?? 0} / ${data.health_summary.red ?? 0}`,
          },
        ].map((stat, index) => (
          <Grid key={stat.label} size={{ xs: 6, md: 4, lg: 2 }}>
            <KpiTile label={stat.label} value={stat.value} warn={stat.warn} delayMs={index * 40} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 6 }}>
          <WallPanel
            title="Deliveries coming up"
            subtitle="Due within 7 days — chase owners while there is runway"
            accent={designTokens.semantic.primary}
            delayMs={80}
          >
            <DeliveryRows
              rows={upcoming}
              emptyLabel="No upcoming deliveries in the next 7 days."
              tone="ok"
            />
          </WallPanel>
        </Grid>
        <Grid size={{ xs: 12, lg: 6 }}>
          <WallPanel
            title="Late deliveries"
            subtitle="Past due — priority follow-up for Program / Engineering managers"
            accent={designTokens.semantic.danger}
            delayMs={120}
          >
            <DeliveryRows
              rows={late}
              emptyLabel="No late deliveries. Keep watching due dates as work progresses."
              tone="danger"
            />
          </WallPanel>
        </Grid>
      </Grid>

      <WallPanel
        title="Team-wise live projects"
        subtitle="Active & on-hold tools by delivery team — red and yellow edged first"
        accent={designTokens.semantic.success}
        delayMs={160}
      >
        <TeamLiveWall teams={teamsLive} />
      </WallPanel>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <WallPanel title="Capacity snapshot" subtitle="This week" delayMs={200}>
            {gridQuery.isLoading ? (
              <Typography sx={{ color: WALL.muted }}>Loading capacity…</Typography>
            ) : gridQuery.error ? (
              <Typography sx={{ color: WALL.muted }}>Capacity grid unavailable</Typography>
            ) : (
              <Stack spacing={1.25}>
                <Typography sx={{ color: WALL.text, fontSize: '1.35rem', fontWeight: 800 }}>
                  {designers.length}{' '}
                  <Box component="span" sx={{ color: WALL.muted, fontSize: '1rem', fontWeight: 600 }}>
                    designers on board
                  </Box>
                </Typography>
                <Typography
                  sx={{
                    fontSize: '1.25rem',
                    fontWeight: 800,
                    color: overloaded > 0 ? '#fbbf24' : WALL.text,
                  }}
                >
                  {overloaded}{' '}
                  <Box component="span" sx={{ color: WALL.muted, fontSize: '1rem', fontWeight: 600 }}>
                    at or over capacity
                  </Box>
                </Typography>
                <Typography sx={{ color: WALL.muted, fontSize: '0.9rem' }}>
                  Assignments cannot be changed from this monitor account.
                </Typography>
              </Stack>
            )}
          </WallPanel>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <WallPanel title="Recent releases" subtitle="Last 30 days" delayMs={240}>
            <Stack spacing={1}>
              {(data.recent_releases ?? []).length ? (
                data.recent_releases.map((row, index) => (
                  <Box
                    key={index}
                    sx={{
                      px: 1.5,
                      py: 1.1,
                      borderRadius: 2,
                      bgcolor: WALL.soft,
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 1,
                    }}
                  >
                    <Typography sx={{ fontWeight: 800, color: WALL.text, fontSize: '1.05rem' }}>
                      {String(row.tool_number ?? '—')}
                    </Typography>
                    <Typography sx={{ color: WALL.muted, fontWeight: 600 }}>
                      {row.completed_at ? String(row.completed_at) : ''}
                    </Typography>
                  </Box>
                ))
              ) : (
                <Typography sx={{ color: WALL.muted }}>No releases in the last 30 days</Typography>
              )}
            </Stack>
          </WallPanel>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <WallPanel title="Customer load" subtitle="Share of active engineering work" delayMs={280}>
            <Stack spacing={1}>
              {(data.customer_distribution ?? []).length ? (
                data.customer_distribution.map((row, index) => (
                  <Box
                    key={index}
                    sx={{
                      px: 1.5,
                      py: 1.1,
                      borderRadius: 2,
                      bgcolor: WALL.soft,
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 1,
                    }}
                  >
                    <Typography sx={{ fontWeight: 700, color: WALL.text }} noWrap>
                      {String(row.customer_name ?? row.name ?? 'Customer')}
                    </Typography>
                    <Typography sx={{ fontWeight: 800, color: '#93c5fd' }}>
                      {String(row.percent ?? row.share ?? row.hours ?? '—')}
                    </Typography>
                  </Box>
                ))
              ) : (
                <Typography sx={{ color: WALL.muted }}>No customer distribution available</Typography>
              )}
            </Stack>
          </WallPanel>
        </Grid>
      </Grid>
    </Stack>
  );
}
