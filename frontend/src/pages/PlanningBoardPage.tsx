import { Box, Chip, LinearProgress, Stack, Typography } from '@mui/material';
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from 'react';
import { useQuery } from '@tanstack/react-query';
import { aiQueryKeys, fetchExecutiveWall } from '../api/ai';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { designTokens } from '../theme/designTokens';
import type { WallProjectCard, WallTeamLiveBlock } from '../types/Ai';
import { formatDate, formatDisplayValue } from '../utils/format';

const WALL = {
  panel: 'rgba(30, 41, 59, 0.94)',
  panelBorder: 'rgba(148, 163, 184, 0.22)',
  text: '#f8fafc',
  muted: 'rgba(203, 213, 225, 0.88)',
  soft: 'rgba(148, 163, 184, 0.14)',
} as const;

const PROJECT_ROW_PX = 58;
const TEAM_HEADER_PX = 36;
const RAIL_ROW_PX = 44;
const RAIL_SECTION_HEADER_PX = 28;

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

function useFitCount(
  ref: RefObject<HTMLElement | null>,
  rowHeight: number,
  headerReserve: number,
  fallback: number,
) {
  const [count, setCount] = useState(fallback);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return;

    const measure = () => {
      const height = el.clientHeight;
      const available = Math.max(0, height - headerReserve);
      setCount(Math.max(1, Math.floor(available / rowHeight)));
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, rowHeight, headerReserve]);

  return count;
}

function PanelShell({
  title,
  accent,
  children,
  rightSlot,
}: {
  title: string;
  accent?: string;
  children: ReactNode;
  rightSlot?: ReactNode;
}) {
  return (
    <Box
      sx={{
        height: '100%',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        p: 1.25,
        borderRadius: 2,
        bgcolor: WALL.panel,
        border: `1px solid ${WALL.panelBorder}`,
        borderTop: accent ? `3px solid ${accent}` : undefined,
        overflow: 'hidden',
      }}
    >
      <Stack
        direction="row"
        spacing={1}
        sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 0.75, flexShrink: 0 }}
      >
        <Typography sx={{ fontWeight: 800, fontSize: '0.95rem', color: WALL.text, letterSpacing: '-0.01em' }}>
          {title}
        </Typography>
        {rightSlot}
      </Stack>
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>{children}</Box>
    </Box>
  );
}

function KpiStrip({
  items,
}: {
  items: { label: string; value: string | number; warn?: boolean }[];
}) {
  return (
    <Box
      sx={{
        flexShrink: 0,
        display: 'grid',
        gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))`,
        gap: 1,
      }}
    >
      {items.map((stat) => (
        <Box
          key={stat.label}
          sx={{
            px: 1.25,
            py: 0.7,
            borderRadius: 1.5,
            bgcolor: WALL.panel,
            border: `1px solid ${WALL.panelBorder}`,
            borderLeft: `4px solid ${stat.warn ? designTokens.semantic.warning : designTokens.semantic.primary}`,
            display: 'flex',
            alignItems: 'baseline',
            gap: 1,
            minWidth: 0,
          }}
        >
          <Typography
            sx={{
              fontWeight: 800,
              fontSize: { xs: '1.15rem', md: '1.45rem' },
              lineHeight: 1,
              color: stat.warn ? '#fbbf24' : WALL.text,
              flexShrink: 0,
            }}
          >
            {stat.value}
          </Typography>
          <Typography
            sx={{
              color: WALL.muted,
              fontWeight: 700,
              fontSize: { xs: '0.65rem', md: '0.72rem' },
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              lineHeight: 1.2,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {stat.label}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

function CompactDeliveryList({
  rows,
  emptyLabel,
  tone,
  maxRows,
}: {
  rows: WallProjectCard[];
  emptyLabel: string;
  tone: 'ok' | 'danger';
  maxRows: number;
}) {
  const visible = rows.slice(0, maxRows);
  const hidden = Math.max(0, rows.length - visible.length);

  if (!rows.length) {
    return (
      <Typography sx={{ color: WALL.muted, fontSize: '0.78rem', fontWeight: 600 }}>
        {emptyLabel}
      </Typography>
    );
  }

  return (
    <Stack spacing={0.5} sx={{ height: '100%' }}>
      {visible.map((row) => {
        return (
          <Box
            key={`${row.tool_number}-${row.due_date ?? ''}-${row.project_id ?? ''}`}
            sx={{
              px: 0.9,
              py: 0.45,
              borderRadius: 1,
              bgcolor: tone === 'danger' ? 'rgba(220, 38, 38, 0.12)' : 'rgba(37, 99, 235, 0.10)',
              borderLeft: `3px solid ${
                tone === 'danger' ? designTokens.semantic.danger : designTokens.semantic.primary
              }`,
              minHeight: RAIL_ROW_PX - 6,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}
          >
            <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 0.5, alignItems: 'baseline' }}>
              <Typography sx={{ fontWeight: 800, fontSize: '0.88rem', color: WALL.text }} noWrap>
                {row.tool_number}
              </Typography>
              <Typography sx={{ fontWeight: 700, fontSize: '0.72rem', color: WALL.muted, whiteSpace: 'nowrap' }}>
                {row.due_date ? formatDate(row.due_date) : '—'}
              </Typography>
            </Stack>
            <Typography sx={{ color: WALL.muted, fontSize: '0.7rem', fontWeight: 600 }} noWrap>
              {formatDisplayValue(row.designer_name)} · {(row.health ?? 'green').toUpperCase()}
            </Typography>
          </Box>
        );
      })}
      {hidden > 0 ? (
        <Typography sx={{ color: WALL.muted, fontSize: '0.72rem', fontWeight: 700 }}>+{hidden} more</Typography>
      ) : null}
    </Stack>
  );
}

function ProjectRow({ project }: { project: WallProjectCard }) {
  const health = healthTone(project.health);
  const stage = project.current_milestone || humanizeStage(project.project_stage);
  const percent = Math.max(0, Math.min(100, Number(project.progress_percent ?? 0)));

  return (
    <Box
      sx={{
        px: 1,
        py: 0.45,
        borderRadius: 1.25,
        bgcolor: WALL.soft,
        borderLeft: `4px solid ${health.main}`,
        minHeight: PROJECT_ROW_PX - 6,
        display: 'grid',
        gridTemplateColumns: '72px minmax(0, 1.1fr) minmax(0, 1fr) 88px',
        gap: 0.75,
        alignItems: 'center',
      }}
    >
      <Typography sx={{ fontWeight: 800, color: WALL.text, fontSize: '0.95rem' }} noWrap>
        {project.tool_number}
      </Typography>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontWeight: 700, color: WALL.text, fontSize: '0.78rem' }} noWrap>
          {formatDisplayValue(stage)}
        </Typography>
        <Typography sx={{ color: WALL.muted, fontSize: '0.7rem', fontWeight: 600 }} noWrap>
          {contributorLabel(project)}
        </Typography>
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', mb: 0.25 }}>
          <Typography sx={{ color: WALL.muted, fontSize: '0.65rem', fontWeight: 700 }}>DONE</Typography>
          <Typography sx={{ color: WALL.text, fontSize: '0.75rem', fontWeight: 800 }}>{Math.round(percent)}%</Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={percent}
          sx={{
            height: 7,
            borderRadius: 999,
            bgcolor: 'rgba(15, 23, 42, 0.55)',
            '& .MuiLinearProgress-bar': { borderRadius: 999, bgcolor: health.main },
          }}
        />
      </Box>
      <Typography sx={{ color: WALL.muted, fontWeight: 700, fontSize: '0.7rem', textAlign: 'right' }} noWrap>
        {project.due_date ? formatDate(project.due_date) : '—'}
      </Typography>
    </Box>
  );
}

function TeamColumn({ team, maxProjects }: { team: WallTeamLiveBlock; maxProjects: number }) {
  const visible = team.projects.slice(0, maxProjects);
  const hidden = Math.max(0, team.projects.length - visible.length);

  return (
    <Box
      sx={{
        height: '100%',
        minHeight: 0,
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        p: 1,
        borderRadius: 1.5,
        bgcolor: 'rgba(15, 23, 42, 0.55)',
        border: `1px solid ${WALL.panelBorder}`,
        overflow: 'hidden',
      }}
    >
      <Stack
        direction="row"
        spacing={0.75}
        useFlexGap
        sx={{ mb: 0.75, alignItems: 'center', flexWrap: 'nowrap', flexShrink: 0, minHeight: TEAM_HEADER_PX - 8 }}
      >
        <Typography sx={{ fontWeight: 800, fontSize: '0.95rem', color: WALL.text }} noWrap>
          {team.team_name}
        </Typography>
        <Chip
          size="small"
          label={`${team.active_count}`}
          sx={{ height: 22, fontWeight: 800, bgcolor: 'rgba(37, 99, 235, 0.22)', color: '#93c5fd' }}
        />
        {team.red_count > 0 ? (
          <Chip
            size="small"
            label={`R${team.red_count}`}
            sx={{ height: 22, fontWeight: 800, bgcolor: designTokens.health.red.soft, color: designTokens.health.red.main }}
          />
        ) : null}
        {team.yellow_count > 0 ? (
          <Chip
            size="small"
            label={`Y${team.yellow_count}`}
            sx={{
              height: 22,
              fontWeight: 800,
              bgcolor: designTokens.health.yellow.soft,
              color: designTokens.health.yellow.main,
            }}
          />
        ) : null}
        {hidden > 0 ? (
          <Typography sx={{ color: WALL.muted, fontSize: '0.7rem', fontWeight: 700, ml: 'auto' }}>
            +{hidden}
          </Typography>
        ) : null}
      </Stack>
      <Stack spacing={0.55} sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {visible.length ? (
          visible.map((project) => (
            <ProjectRow key={project.project_id ?? project.tool_number} project={project} />
          ))
        ) : (
          <Typography sx={{ color: WALL.muted, fontSize: '0.8rem' }}>No live tools</Typography>
        )}
      </Stack>
    </Box>
  );
}

export default function PlanningBoardPage() {
  const teamsRef = useRef<HTMLDivElement | null>(null);
  const lateRef = useRef<HTMLDivElement | null>(null);
  const upcomingRef = useRef<HTMLDivElement | null>(null);

  const maxProjects = useFitCount(teamsRef, PROJECT_ROW_PX, TEAM_HEADER_PX + 8, 5);
  const maxLate = useFitCount(lateRef, RAIL_ROW_PX, RAIL_SECTION_HEADER_PX, 5);
  const maxUpcoming = useFitCount(upcomingRef, RAIL_ROW_PX, RAIL_SECTION_HEADER_PX, 5);

  const wallQuery = useQuery({
    queryKey: aiQueryKeys.executiveWall,
    queryFn: fetchExecutiveWall,
    refetchInterval: 60_000,
  });

  const teamsLive = useMemo(() => {
    const teams = wallQuery.data?.teams_live ?? [];
    // Prefer teams with risk first so the fitted viewport shows what matters.
    return [...teams].sort((a, b) => {
      const score = (t: WallTeamLiveBlock) => t.red_count * 10 + t.yellow_count;
      return score(b) - score(a) || a.team_name.localeCompare(b.team_name);
    });
  }, [wallQuery.data?.teams_live]);

  if (wallQuery.isLoading) {
    return (
      <Box sx={{ height: '100%', color: WALL.text, display: 'grid', placeItems: 'center' }}>
        <LoadingState message="Loading planning board…" />
      </Box>
    );
  }
  if (wallQuery.error) {
    return <ErrorState error={wallQuery.error} title="Unable to load planning board" />;
  }

  const data = wallQuery.data!;
  const upcoming = data.upcoming_deliveries ?? [];
  const late = data.late_deliveries ?? [];
  const refreshed = data.refreshed_at
    ? new Date(data.refreshed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '—';

  // Fit team columns into one row when possible (wall TV is wide).
  const teamCols = Math.min(Math.max(teamsLive.length, 1), 4);
  const visibleTeams = teamsLive.slice(0, teamCols);
  const hiddenTeams = Math.max(0, teamsLive.length - visibleTeams.length);

  return (
    <Box
      sx={{
        height: '100%',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        overflow: 'hidden',
      }}
    >
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexShrink: 0 }}>
        <Typography sx={{ color: WALL.muted, fontWeight: 600, fontSize: '0.78rem', flex: 1 }} noWrap>
          Single-screen wall · stage · designers · completion · synced {refreshed}
        </Typography>
        {hiddenTeams > 0 ? (
          <Chip
            size="small"
            label={`+${hiddenTeams} teams off-screen (risk sorted)`}
            sx={{ bgcolor: WALL.soft, color: WALL.muted, fontWeight: 700, height: 24 }}
          />
        ) : null}
      </Stack>

      <KpiStrip
        items={[
          { label: 'Active', value: data.active_projects },
          { label: 'Late MS', value: data.late_milestones, warn: data.late_milestones > 0 },
          { label: 'Late tools', value: late.length, warn: late.length > 0 },
          { label: 'Due 7d', value: upcoming.length },
          {
            label: 'G / Y / R',
            value: `${data.health_summary.green ?? 0}/${data.health_summary.yellow ?? 0}/${data.health_summary.red ?? 0}`,
          },
        ]}
      />

      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: 'minmax(0, 1fr) 260px' },
          gap: 1,
          overflow: 'hidden',
        }}
      >
        <PanelShell
          title="Team-wise live"
          accent={designTokens.semantic.success}
          rightSlot={
            <Typography sx={{ color: WALL.muted, fontSize: '0.7rem', fontWeight: 700 }}>
              Showing {maxProjects}/team · red/yellow first
            </Typography>
          }
        >
          {visibleTeams.length ? (
            <Box
              ref={teamsRef}
              sx={{
                height: '100%',
                minHeight: 0,
                display: 'grid',
                gridTemplateColumns: `repeat(${visibleTeams.length}, minmax(0, 1fr))`,
                gap: 1,
                overflow: 'hidden',
              }}
            >
              {visibleTeams.map((team) => (
                <TeamColumn
                  key={`${team.team_id ?? 'none'}-${team.team_name}`}
                  team={team}
                  maxProjects={maxProjects}
                />
              ))}
            </Box>
          ) : (
            <Typography sx={{ color: WALL.muted }}>No live projects on the board right now.</Typography>
          )}
        </PanelShell>

        <Box
          sx={{
            minHeight: 0,
            display: { xs: 'none', lg: 'grid' },
            gridTemplateRows: '1fr 1fr',
            gap: 1,
            overflow: 'hidden',
          }}
        >
          <PanelShell title="Late" accent={designTokens.semantic.danger}>
            <Box ref={lateRef} sx={{ height: '100%', minHeight: 0, overflow: 'hidden' }}>
              <CompactDeliveryList rows={late} emptyLabel="None late." tone="danger" maxRows={maxLate} />
            </Box>
          </PanelShell>
          <PanelShell title="Coming up" accent={designTokens.semantic.primary}>
            <Box ref={upcomingRef} sx={{ height: '100%', minHeight: 0, overflow: 'hidden' }}>
              <CompactDeliveryList
                rows={upcoming}
                emptyLabel="None in 7 days."
                tone="ok"
                maxRows={maxUpcoming}
              />
            </Box>
          </PanelShell>
        </Box>
      </Box>
    </Box>
  );
}
