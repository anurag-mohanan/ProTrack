import { Box, Chip, Grid, LinearProgress, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { keyframes } from '@mui/system';
import { aiQueryKeys, fetchExecutiveWall } from '../api/ai';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { designTokens } from '../theme/designTokens';
import type { WallProjectCard, WallTeamLiveBlock } from '../types/Ai';
import { formatDate, formatDisplayValue } from '../utils/format';

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

function humanizeStage(value?: string | null) {
  if (!value) return '—';
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function contributorLabel(project: WallProjectCard) {
  const names = (project.contributor_names ?? []).filter(Boolean);
  if (names.length) return names.join(' · ');
  return formatDisplayValue(project.designer_name);
}

function WallPanel({
  title,
  subtitle,
  accent,
  children,
  delayMs = 0,
  dense,
}: {
  title: string;
  subtitle?: string;
  accent?: string;
  children: ReactNode;
  delayMs?: number;
  dense?: boolean;
}) {
  return (
    <Box
      sx={{
        height: '100%',
        p: dense ? { xs: 1.5, md: 1.75 } : { xs: 2, md: 2.5 },
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
          fontSize: dense ? { xs: '0.95rem', md: '1.05rem' } : { xs: '1.2rem', md: '1.45rem' },
          color: WALL.text,
          letterSpacing: '-0.02em',
        }}
      >
        {title}
      </Typography>
      {subtitle ? (
        <Typography
          sx={{
            color: WALL.muted,
            mb: dense ? 1.25 : 1.75,
            mt: 0.35,
            fontSize: dense ? '0.8rem' : '0.95rem',
            fontWeight: 500,
          }}
        >
          {subtitle}
        </Typography>
      ) : (
        <Box sx={{ mb: dense ? 1 : 1.5 }} />
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
        p: { xs: 1.75, md: 2 },
        borderRadius: 3,
        bgcolor: WALL.panel,
        border: `1px solid ${WALL.panelBorder}`,
        borderLeft: `5px solid ${warn ? designTokens.semantic.warning : designTokens.semantic.primary}`,
        minHeight: { xs: 96, md: 112 },
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
          fontSize: { xs: '1.75rem', md: '2.25rem', xl: '2.6rem' },
          lineHeight: 1,
          color: warn ? '#fbbf24' : WALL.text,
          letterSpacing: '-0.03em',
        }}
      >
        {value}
      </Typography>
      <Typography
        sx={{
          mt: 0.85,
          color: WALL.muted,
          fontWeight: 700,
          fontSize: { xs: '0.75rem', md: '0.85rem' },
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        {label}
      </Typography>
    </Box>
  );
}

function CompactDeliveryList({
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
      <Typography sx={{ color: WALL.muted, fontSize: '0.85rem', fontWeight: 600, py: 1 }}>
        {emptyLabel}
      </Typography>
    );
  }

  return (
    <Stack spacing={0.85}>
      {rows.slice(0, 8).map((row) => {
        const health = healthTone(row.health);
        return (
          <Box
            key={`${row.tool_number}-${row.due_date ?? ''}-${row.project_id ?? ''}`}
            sx={{
              px: 1.15,
              py: 0.9,
              borderRadius: 1.5,
              bgcolor: tone === 'danger' ? 'rgba(220, 38, 38, 0.12)' : 'rgba(37, 99, 235, 0.10)',
              border: `1px solid ${
                tone === 'danger' ? 'rgba(248, 113, 113, 0.28)' : 'rgba(96, 165, 250, 0.28)'
              }`,
              borderLeft: `3px solid ${tone === 'danger' ? designTokens.semantic.danger : designTokens.semantic.primary}`,
            }}
          >
            <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
              <Typography sx={{ fontWeight: 800, fontSize: '0.95rem', color: WALL.text }}>
                {row.tool_number}
              </Typography>
              <Typography sx={{ fontWeight: 700, fontSize: '0.8rem', color: WALL.muted, whiteSpace: 'nowrap' }}>
                {row.due_date ? formatDate(row.due_date) : '—'}
              </Typography>
            </Stack>
            <Typography sx={{ color: WALL.muted, fontSize: '0.78rem', fontWeight: 600 }} noWrap>
              {formatDisplayValue(row.customer_name)}
            </Typography>
            <Stack direction="row" spacing={0.75} sx={{ mt: 0.4, alignItems: 'center' }}>
              <Typography sx={{ color: WALL.text, fontSize: '0.75rem', fontWeight: 600 }} noWrap>
                {formatDisplayValue(row.designer_name)}
              </Typography>
              <Chip
                size="small"
                label={(row.health ?? 'green').toUpperCase()}
                sx={{
                  height: 20,
                  fontSize: '0.65rem',
                  fontWeight: 800,
                  bgcolor: health.soft,
                  color: health.main,
                }}
              />
            </Stack>
          </Box>
        );
      })}
    </Stack>
  );
}

function ProgressBar({ percent, health }: { percent: number; health?: string | null }) {
  const tone = healthTone(health);
  const value = Math.max(0, Math.min(100, Number.isFinite(percent) ? percent : 0));
  return (
    <Stack spacing={0.45} sx={{ minWidth: 0 }}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
        <Typography sx={{ color: WALL.muted, fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.04em' }}>
          COMPLETION
        </Typography>
        <Typography sx={{ color: WALL.text, fontWeight: 800, fontSize: '0.95rem' }}>
          {Math.round(value)}%
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={value}
        sx={{
          height: 10,
          borderRadius: 999,
          bgcolor: 'rgba(15, 23, 42, 0.55)',
          '& .MuiLinearProgress-bar': {
            borderRadius: 999,
            bgcolor: tone.main,
          },
        }}
      />
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
              animationDelay: `${80 + index * 40}ms`,
            }}
          >
            <Stack
              direction="row"
              spacing={1}
              useFlexGap
              sx={{ mb: 1.5, alignItems: 'center', flexWrap: 'wrap' }}
            >
              <Typography sx={{ fontWeight: 800, fontSize: { xs: '1.2rem', md: '1.35rem' }, color: WALL.text, mr: 0.5 }}>
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

            <Stack spacing={1.25}>
              {team.projects.slice(0, 10).map((project) => {
                const health = healthTone(project.health);
                const stage = project.current_milestone || humanizeStage(project.project_stage);
                return (
                  <Box
                    key={project.project_id ?? project.tool_number}
                    sx={{
                      px: 1.75,
                      py: 1.35,
                      borderRadius: 2,
                      bgcolor: WALL.soft,
                      borderLeft: `5px solid ${health.main}`,
                    }}
                  >
                    <Stack
                      direction={{ xs: 'column', sm: 'row' }}
                      spacing={1}
                      sx={{ justifyContent: 'space-between', alignItems: { sm: 'flex-start' }, mb: 0.85 }}
                    >
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'baseline', flexWrap: 'wrap' }} useFlexGap>
                          <Typography sx={{ fontWeight: 800, color: WALL.text, fontSize: { xs: '1.15rem', md: '1.3rem' } }}>
                            {project.tool_number}
                          </Typography>
                          <Typography sx={{ fontWeight: 700, color: WALL.muted, fontSize: '0.95rem' }} noWrap>
                            {formatDisplayValue(project.customer_name)}
                          </Typography>
                        </Stack>
                        <Typography
                          sx={{
                            mt: 0.55,
                            color: WALL.text,
                            fontWeight: 700,
                            fontSize: { xs: '0.95rem', md: '1.05rem' },
                          }}
                          noWrap
                        >
                          Stage: {formatDisplayValue(stage)}
                        </Typography>
                        <Typography sx={{ mt: 0.35, color: WALL.muted, fontSize: '0.9rem', fontWeight: 600 }} noWrap>
                          Designers: {contributorLabel(project)}
                        </Typography>
                      </Box>
                      <Stack spacing={0.5} sx={{ alignItems: { xs: 'flex-start', sm: 'flex-end' }, flexShrink: 0 }}>
                        <Chip
                          size="small"
                          label={(project.health ?? 'green').toUpperCase()}
                          sx={{ fontWeight: 800, bgcolor: health.soft, color: health.main }}
                        />
                        <Typography sx={{ color: WALL.muted, fontWeight: 700, fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                          Due {project.due_date ? formatDate(project.due_date) : '—'}
                        </Typography>
                      </Stack>
                    </Stack>
                    <ProgressBar percent={Number(project.progress_percent ?? 0)} health={project.health} />
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
  const refreshed = data.refreshed_at
    ? new Date(data.refreshed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '—';

  return (
    <Stack spacing={{ xs: 2, md: 2.5 }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1}
        sx={{ justifyContent: 'space-between', alignItems: { md: 'center' } }}
      >
        <Box>
          <Typography sx={{ color: WALL.text, fontWeight: 800, fontSize: { xs: '1.1rem', md: '1.25rem' } }}>
            Team floor — live tools, stage & designers
          </Typography>
          <Typography sx={{ color: WALL.muted, fontWeight: 500 }}>
            Auto-refresh every 60s · read-only wall display · deliveries on the right rail
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
          { label: 'Late Milestones', value: data.late_milestones, warn: data.late_milestones > 0 },
          { label: 'Late Deliveries', value: late.length, warn: late.length > 0 },
          { label: 'Due in 7 Days', value: upcoming.length },
          {
            label: 'Health G / Y / R',
            value: `${data.health_summary.green ?? 0} / ${data.health_summary.yellow ?? 0} / ${data.health_summary.red ?? 0}`,
          },
        ].map((stat, index) => (
          <Grid key={stat.label} size={{ xs: 6, sm: 4, md: 2.4 }}>
            <KpiTile label={stat.label} value={stat.value} warn={stat.warn} delayMs={index * 40} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2} sx={{ alignItems: 'stretch' }}>
        <Grid size={{ xs: 12, lg: 9 }}>
          <WallPanel
            title="Team-wise live projects"
            subtitle="Hero view — stage, designers on the tool, and milestone completion"
            accent={designTokens.semantic.success}
            delayMs={80}
          >
            <TeamLiveWall teams={teamsLive} />
          </WallPanel>
        </Grid>

        <Grid size={{ xs: 12, lg: 3 }}>
          <Stack spacing={2} sx={{ height: '100%' }}>
            <WallPanel
              title="Late deliveries"
              subtitle="Past due — chase first"
              accent={designTokens.semantic.danger}
              delayMs={120}
              dense
            >
              <CompactDeliveryList
                rows={late}
                emptyLabel="No late deliveries."
                tone="danger"
              />
            </WallPanel>
            <WallPanel
              title="Coming up"
              subtitle="Due within 7 days"
              accent={designTokens.semantic.primary}
              delayMs={160}
              dense
            >
              <CompactDeliveryList
                rows={upcoming}
                emptyLabel="Nothing due in the next 7 days."
                tone="ok"
              />
            </WallPanel>
          </Stack>
        </Grid>
      </Grid>
    </Stack>
  );
}
