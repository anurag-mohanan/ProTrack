import { Box, Button, Chip, LinearProgress, Stack, Typography } from '@mui/material';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import { useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { aiQueryKeys, fetchExecutiveWall } from '../api/ai';
import { fetchTeams } from '../api/lookups';
import { RoomTeamsDialog } from '../components/planningBoard/RoomTeamsDialog';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { designTokens } from '../theme/designTokens';
import type { WallProjectCard, WallTeamLiveBlock } from '../types/Ai';
import { formatDate, formatDisplayValue } from '../utils/format';
import {
  buildTeamsSearchParam,
  loadRoomName,
  resolveRoomTeamIdsFromSearch,
  saveRoomName,
  saveRoomTeamIds,
} from '../utils/planningBoardRoom';

const WALL = {
  panel: 'rgba(30, 41, 59, 0.94)',
  panelBorder: 'rgba(148, 163, 184, 0.22)',
  text: '#f8fafc',
  muted: 'rgba(203, 213, 225, 0.88)',
  soft: 'rgba(148, 163, 184, 0.14)',
} as const;

const RAIL_ROW_PX = 42;
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

function workersLabel(project: WallProjectCard) {
  const names = [
    project.designer_name,
    project.surfacer_name,
    ...(project.contributor_names ?? []),
  ]
    .map((name) => (name || '').trim())
    .filter(Boolean);
  const unique: string[] = [];
  for (const name of names) {
    if (!unique.includes(name)) unique.push(name);
  }
  // Prefer explicit designer + surfacer (max 2) when both fields exist.
  if (project.designer_name || project.surfacer_name) {
    return [project.designer_name, project.surfacer_name]
      .map((name) => (name || '').trim())
      .filter(Boolean)
      .join(' · ') || '—';
  }
  return unique.slice(0, 2).join(' · ') || '—';
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
      {visible.map((row) => (
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
      ))}
      {hidden > 0 ? (
        <Typography sx={{ color: WALL.muted, fontSize: '0.72rem', fontWeight: 700 }}>+{hidden} more</Typography>
      ) : null}
    </Stack>
  );
}

function formatHours(value: number | null | undefined) {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return '0';
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function HoursVarianceLine({ project }: { project: WallProjectCard }) {
  const quoted = Number(project.quoted_hours ?? 0);
  const actual = Number(project.actual_hours ?? 0);
  const variancePct = project.variance_percent;
  const over = typeof variancePct === 'number' && variancePct > 0;
  const under = typeof variancePct === 'number' && variancePct < 0;
  const varianceColor = over ? '#fca5a5' : under ? '#86efac' : WALL.muted;
  const varianceLabel =
    typeof variancePct === 'number'
      ? `${variancePct > 0 ? '+' : ''}${Math.round(variancePct)}%`
      : 'n/a';

  return (
    <Typography sx={{ color: WALL.muted, fontSize: '0.68rem', fontWeight: 700 }} noWrap>
      Q {formatHours(quoted)}h · A {formatHours(actual)}h ·{' '}
      <Box component="span" sx={{ color: varianceColor, fontWeight: 800 }}>
        {varianceLabel}
      </Box>
    </Typography>
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
        minHeight: 52,
        display: 'grid',
        gridTemplateColumns: '72px minmax(0, 1.2fr) minmax(0, 0.95fr) 84px',
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
          {project.complexity
            ? ` · ${String(project.complexity).replace(/^./, (c) => c.toUpperCase())}`
            : ''}
        </Typography>
        <Typography sx={{ color: WALL.muted, fontSize: '0.7rem', fontWeight: 600 }} noWrap>
          {workersLabel(project)}
        </Typography>
        <HoursVarianceLine project={project} />
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', mb: 0.2 }}>
          <Typography sx={{ color: WALL.muted, fontSize: '0.62rem', fontWeight: 700 }}>DONE</Typography>
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

function isOnHold(project: WallProjectCard) {
  return (project.execution_status ?? '').toLowerCase() === 'on_hold';
}

function SubcategoryLabel({ label, count }: { label: string; count: number }) {
  return (
    <Stack
      direction="row"
      spacing={0.75}
      sx={{
        alignItems: 'center',
        pt: 0.35,
        pb: 0.15,
        position: 'sticky',
        top: 0,
        zIndex: 1,
        bgcolor: 'rgba(15, 23, 42, 0.92)',
      }}
    >
      <Typography
        sx={{
          color: WALL.muted,
          fontSize: '0.68rem',
          fontWeight: 800,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </Typography>
      <Chip
        size="small"
        label={count}
        sx={{
          height: 18,
          fontSize: '0.65rem',
          fontWeight: 800,
          bgcolor: WALL.soft,
          color: WALL.muted,
        }}
      />
    </Stack>
  );
}

function TeamColumn({ team }: { team: WallTeamLiveBlock }) {
  const working = team.projects.filter((project) => !isOnHold(project));
  const onHold = team.projects.filter((project) => isOnHold(project));
  const workingCount = team.active_count ?? working.length;
  const holdCount = team.on_hold_count ?? onHold.length;

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
      <Box sx={{ flexShrink: 0, mb: 0.75 }}>
        <Stack direction="row" spacing={0.75} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography sx={{ fontWeight: 800, fontSize: '1rem', color: WALL.text }} noWrap>
            {team.team_name}
          </Typography>
          <Chip
            size="small"
            label={`${workingCount} active`}
            sx={{ height: 22, fontWeight: 800, bgcolor: 'rgba(37, 99, 235, 0.22)', color: '#93c5fd' }}
          />
          {holdCount > 0 ? (
            <Chip
              size="small"
              label={`${holdCount} hold`}
              sx={{
                height: 22,
                fontWeight: 800,
                bgcolor: 'rgba(148, 163, 184, 0.22)',
                color: '#cbd5e1',
              }}
            />
          ) : null}
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
        </Stack>
        <Typography sx={{ mt: 0.35, color: WALL.muted, fontSize: '0.72rem', fontWeight: 600 }} noWrap>
          EM: {formatDisplayValue(team.engineering_manager_name)}
          {'  ·  '}
          Design Leader: {formatDisplayValue(team.design_leader_name)}
        </Typography>
      </Box>

      <Stack
        spacing={0.45}
        sx={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          overflowX: 'hidden',
          pr: 0.25,
          scrollbarWidth: 'thin',
          '&::-webkit-scrollbar': { width: 6 },
          '&::-webkit-scrollbar-thumb': {
            bgcolor: 'rgba(148, 163, 184, 0.35)',
            borderRadius: 999,
          },
        }}
      >
        {working.length || onHold.length ? (
          <>
            {working.length ? (
              <>
                <SubcategoryLabel label="Active" count={working.length} />
                {working.map((project) => (
                  <ProjectRow key={project.project_id ?? project.tool_number} project={project} />
                ))}
              </>
            ) : null}
            {onHold.length ? (
              <>
                <SubcategoryLabel label="On hold" count={onHold.length} />
                {onHold.map((project) => (
                  <Box
                    key={project.project_id ?? `hold-${project.tool_number}`}
                    sx={{ opacity: 0.88 }}
                  >
                    <ProjectRow project={project} />
                  </Box>
                ))}
              </>
            ) : null}
          </>
        ) : (
          <Box
            sx={{
              flex: 1,
              display: 'grid',
              placeItems: 'center',
              borderRadius: 1.25,
              border: `1px dashed ${WALL.panelBorder}`,
              bgcolor: 'rgba(15, 23, 42, 0.35)',
              px: 1.5,
              py: 2,
            }}
          >
            <Typography sx={{ color: WALL.muted, fontSize: '0.85rem', fontWeight: 700, textAlign: 'center' }}>
              No live tools
            </Typography>
            <Typography sx={{ color: WALL.muted, fontSize: '0.72rem', textAlign: 'center', mt: 0.35 }}>
              Team placeholder — waiting for assigned work
            </Typography>
          </Box>
        )}
      </Stack>
    </Box>
  );
}

export default function PlanningBoardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const lateRef = useRef<HTMLDivElement | null>(null);
  const upcomingRef = useRef<HTMLDivElement | null>(null);
  const [roomDialogOpen, setRoomDialogOpen] = useState(false);
  const [roomName, setRoomName] = useState(() => loadRoomName());
  const [selectedTeamIds, setSelectedTeamIds] = useState<string[] | null>(() =>
    resolveRoomTeamIdsFromSearch(window.location.search),
  );

  useEffect(() => {
    setSelectedTeamIds(resolveRoomTeamIdsFromSearch(searchParams.toString()));
  }, [searchParams]);

  const maxLate = useFitCount(lateRef, RAIL_ROW_PX, RAIL_SECTION_HEADER_PX, 6);
  const maxUpcoming = useFitCount(upcomingRef, RAIL_ROW_PX, RAIL_SECTION_HEADER_PX, 6);

  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams', 'planning-board-room'],
    queryFn: fetchTeams,
    staleTime: 60_000,
  });

  const wallQuery = useQuery({
    queryKey: aiQueryKeys.executiveWall(selectedTeamIds),
    queryFn: () => fetchExecutiveWall(selectedTeamIds),
    refetchInterval: 60_000,
  });

  const teamsLive = useMemo(() => {
    const teams = wallQuery.data?.teams_live ?? [];
    // Keep API order (name) but surface risk within columns; room filter already applied server-side.
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

  const visibleTeams = teamsLive;
  const totalVisibleProjects = visibleTeams.reduce((sum, team) => sum + team.projects.length, 0);
  const roomLabel = roomName || (selectedTeamIds ? 'Custom room filter' : 'All company teams');

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
          {roomLabel} · {visibleTeams.length} team columns · synced {refreshed}
        </Typography>
        {selectedTeamIds ? (
          <Chip
            size="small"
            label={`${selectedTeamIds.length} teams selected`}
            sx={{ bgcolor: WALL.soft, color: WALL.muted, fontWeight: 700, height: 24 }}
          />
        ) : (
          <Chip
            size="small"
            label="Showing all teams"
            sx={{ bgcolor: WALL.soft, color: WALL.muted, fontWeight: 700, height: 24 }}
          />
        )}
        <Button
          size="small"
          startIcon={<SettingsOutlinedIcon />}
          onClick={() => setRoomDialogOpen(true)}
          sx={{
            color: WALL.text,
            border: `1px solid ${WALL.panelBorder}`,
            fontWeight: 700,
            textTransform: 'none',
            px: 1.25,
            '&:hover': { bgcolor: WALL.soft },
          }}
        >
          Room teams
        </Button>
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
              {totalVisibleProjects} tools · empty teams stay visible
            </Typography>
          }
        >
          {visibleTeams.length ? (
            <Box
              sx={{
                height: '100%',
                minHeight: 0,
                display: 'grid',
                gridAutoFlow: 'column',
                gridAutoColumns: visibleTeams.length <= 4 ? `minmax(0, 1fr)` : 'minmax(280px, 1fr)',
                gridTemplateColumns:
                  visibleTeams.length <= 4
                    ? `repeat(${visibleTeams.length}, minmax(0, 1fr))`
                    : undefined,
                gap: 1,
                overflowX: visibleTeams.length > 4 ? 'auto' : 'hidden',
                overflowY: 'hidden',
              }}
            >
              {visibleTeams.map((team) => (
                <TeamColumn key={`${team.team_id ?? 'none'}-${team.team_name}`} team={team} />
              ))}
            </Box>
          ) : (
            <Typography sx={{ color: WALL.muted }}>
              No teams selected for this room. Use <strong>Room teams</strong> to choose displays.
            </Typography>
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

      <RoomTeamsDialog
        open={roomDialogOpen}
        teams={teamsQuery.data ?? []}
        selectedIds={selectedTeamIds}
        roomName={roomName}
        onClose={() => setRoomDialogOpen(false)}
        onSave={({ teamIds, roomName: nextName }) => {
          saveRoomTeamIds(teamIds);
          saveRoomName(nextName);
          setSelectedTeamIds(teamIds);
          setRoomName(nextName);
          setRoomDialogOpen(false);
          const params = new URLSearchParams();
          const teamsParam = buildTeamsSearchParam(teamIds);
          if (teamsParam) params.set('teams', teamsParam);
          navigate(
            {
              pathname: '/planning-board',
              search: params.toString() ? `?${params.toString()}` : '',
            },
            { replace: true },
          );
        }}
      />
    </Box>
  );
}
