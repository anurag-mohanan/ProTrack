import { useMemo } from 'react';
import { Box, Chip, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { fetchProjectTimeline, type ProjectTimelineBar } from '../api/calendar';
import { designTokens } from '../theme/designTokens';
import { navigateWithBack } from '../hooks/useBackNavigation';

const DAY_MS = 24 * 60 * 60 * 1000;
const LABEL_WIDTH = 200;
const ROW_HEIGHT = 36;

function parseDay(value: string): Date {
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function addDays(d: Date, days: number): Date {
  const next = new Date(d);
  next.setDate(next.getDate() + days);
  return next;
}

function daysBetween(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / DAY_MS);
}

function healthColor(health?: string) {
  if (health === 'red') return designTokens.health.red.main;
  if (health === 'yellow') return designTokens.health.yellow.main;
  return designTokens.health.green.main;
}

function isOnHold(status?: string) {
  return status === 'on_hold';
}

function defaultWindow() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return {
    from: toIsoDate(addDays(today, -90)),
    to: toIsoDate(addDays(today, 180)),
  };
}

type TeamGroup = {
  key: string;
  title: string;
  bars: ProjectTimelineBar[];
};

function groupByTeam(bars: ProjectTimelineBar[]): TeamGroup[] {
  const map = new Map<string, TeamGroup>();
  for (const bar of bars) {
    const key = bar.team_id ?? 'unassigned';
    const title = bar.team_name?.trim() || 'Unassigned';
    const existing = map.get(key);
    if (existing) {
      existing.bars.push(bar);
    } else {
      map.set(key, { key, title, bars: [bar] });
    }
  }
  return [...map.values()].sort((a, b) => a.title.localeCompare(b.title));
}

function monthTicks(windowStart: Date, totalDays: number): { leftPct: number; label: string }[] {
  const ticks: { leftPct: number; label: string }[] = [];
  for (let i = 0; i <= totalDays; i += 1) {
    const day = addDays(windowStart, i);
    if (day.getDate() === 1 || i === 0) {
      ticks.push({
        leftPct: (i / Math.max(totalDays, 1)) * 100,
        label: day.toLocaleDateString(undefined, { month: 'short', year: '2-digit' }),
      });
    }
  }
  return ticks;
}

function GanttRow({
  bar,
  windowStart,
  totalDays,
  onOpen,
}: {
  bar: ProjectTimelineBar;
  windowStart: Date;
  totalDays: number;
  onOpen: () => void;
}) {
  const start = parseDay(bar.start_date);
  const end = parseDay(bar.end_date);
  const muted = isOnHold(bar.execution_status);
  const missingDue = bar.due_date_missing;

  let offset = daysBetween(windowStart, start);
  let span = Math.max(daysBetween(start, end), missingDue ? 7 : 1);
  if (offset < 0) {
    span += offset;
    offset = 0;
  }
  if (offset + span > totalDays) {
    span = totalDays - offset;
  }
  if (span < 1) span = 1;

  const leftPct = (offset / totalDays) * 100;
  const widthPct = (span / totalDays) * 100;
  const color = healthColor(bar.health);
  const workers = [bar.designer_name, bar.surfacer_name].filter(Boolean).join(' · ');

  return (
    <Box
      onClick={onOpen}
      sx={{
        display: 'grid',
        gridTemplateColumns: `${LABEL_WIDTH}px minmax(0, 1fr)`,
        height: ROW_HEIGHT,
        borderBottom: '1px solid',
        borderColor: 'divider',
        cursor: 'pointer',
        opacity: muted ? 0.75 : 1,
        '&:hover': { bgcolor: 'action.hover' },
      }}
    >
      <Box
        sx={{
          px: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          minWidth: 0,
          position: 'sticky',
          left: 0,
          zIndex: 1,
          bgcolor: 'background.paper',
          borderRight: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography sx={{ fontWeight: 800, fontSize: '0.82rem' }} noWrap>
          {bar.tool_number}
          {bar.customer_name ? (
            <Box component="span" sx={{ color: 'text.secondary', fontWeight: 600 }}>
              {' · '}
              {bar.customer_name}
            </Box>
          ) : null}
        </Typography>
        <Typography variant="caption" color="text.secondary" noWrap>
          {workers || '—'}
          {missingDue ? ' · TBD due' : ''}
        </Typography>
      </Box>
      <Box sx={{ position: 'relative', minWidth: 0 }}>
        <Box
          sx={{
            position: 'absolute',
            top: 8,
            left: `${leftPct}%`,
            width: `${Math.max(widthPct, 0.8)}%`,
            height: 20,
            borderRadius: 1,
            bgcolor: color,
            opacity: missingDue ? 0.55 : 0.9,
            border: missingDue ? '1px dashed rgba(0,0,0,0.35)' : 'none',
            display: 'flex',
            alignItems: 'center',
            px: 0.75,
            overflow: 'hidden',
            minWidth: 28,
          }}
          title={`${bar.start_date} → ${missingDue ? 'TBD' : bar.end_date} · ${Math.round(bar.progress_percent)}%`}
        >
          <Typography
            variant="caption"
            sx={{ color: '#fff', fontWeight: 800, fontSize: '0.65rem', textShadow: '0 1px 1px rgba(0,0,0,0.25)' }}
            noWrap
          >
            {missingDue ? 'TBD' : `${Math.round(bar.progress_percent)}%`}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

export default function EngineeringCalendarPage() {
  const navigate = useNavigate();
  const window = useMemo(() => defaultWindow(), []);

  const query = useQuery({
    queryKey: ['project-timeline', window.from, window.to],
    queryFn: () => fetchProjectTimeline({ from: window.from, to: window.to }),
  });

  const windowStart = useMemo(() => parseDay(window.from), [window.from]);
  const windowEnd = useMemo(() => parseDay(window.to), [window.to]);
  const totalDays = Math.max(daysBetween(windowStart, windowEnd), 1);
  const ticks = useMemo(() => monthTicks(windowStart, totalDays), [windowStart, totalDays]);
  const groups = useMemo(() => groupByTeam(query.data ?? []), [query.data]);
  const todayOffset = daysBetween(windowStart, new Date(new Date().setHours(0, 0, 0, 0)));
  const todayPct = todayOffset >= 0 && todayOffset <= totalDays ? (todayOffset / totalDays) * 100 : null;

  if (query.isLoading) return <LoadingState message="Loading project timeline…" />;

  return (
    <Box>
      <PageHeader
        title="Project Calendar"
        subtitle="Timeline of scoped projects from created date through due date"
      />

      <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap', gap: 1 }}>
        <Chip size="small" label="Green" sx={{ bgcolor: designTokens.health.green.soft, fontWeight: 700 }} />
        <Chip size="small" label="Yellow" sx={{ bgcolor: designTokens.health.yellow.soft, fontWeight: 700 }} />
        <Chip size="small" label="Red" sx={{ bgcolor: designTokens.health.red.soft, fontWeight: 700 }} />
        <Chip size="small" variant="outlined" label="On hold = muted" sx={{ fontWeight: 700 }} />
        <Chip size="small" variant="outlined" label="TBD = missing due date" sx={{ fontWeight: 700 }} />
      </Stack>

      {!groups.length ? (
        <EmptyState title="No projects in range" description="Adjust the date window or create a project." />
      ) : (
        <Box
          sx={{
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            overflow: 'auto',
            maxHeight: 'calc(100vh - 200px)',
            bgcolor: 'background.paper',
          }}
        >
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `${LABEL_WIDTH}px minmax(640px, 1fr)`,
              minWidth: LABEL_WIDTH + 640,
              position: 'sticky',
              top: 0,
              zIndex: 3,
              bgcolor: 'background.paper',
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Box
              sx={{
                px: 1,
                py: 1,
                position: 'sticky',
                left: 0,
                zIndex: 4,
                bgcolor: 'background.paper',
                borderRight: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Typography variant="caption" sx={{ fontWeight: 800, color: 'text.secondary' }}>
                PROJECT
              </Typography>
            </Box>
            <Box sx={{ position: 'relative', height: 36 }}>
              {ticks.map((tick) => (
                <Typography
                  key={`${tick.label}-${tick.leftPct}`}
                  variant="caption"
                  sx={{
                    position: 'absolute',
                    left: `${tick.leftPct}%`,
                    top: 10,
                    transform: 'translateX(4px)',
                    fontWeight: 800,
                    color: 'text.secondary',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {tick.label}
                </Typography>
              ))}
              {todayPct != null ? (
                <Box
                  sx={{
                    position: 'absolute',
                    left: `${todayPct}%`,
                    top: 0,
                    bottom: 0,
                    width: 2,
                    bgcolor: 'primary.main',
                    opacity: 0.7,
                  }}
                />
              ) : null}
            </Box>
          </Box>

          {groups.map((group) => (
            <Box key={group.key}>
              <Box
                sx={{
                  px: 1.25,
                  py: 0.75,
                  bgcolor: 'action.hover',
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  position: 'sticky',
                  top: 36,
                  zIndex: 2,
                  minWidth: LABEL_WIDTH + 640,
                }}
              >
                <Typography sx={{ fontWeight: 800, fontSize: '0.85rem' }}>{group.title}</Typography>
                <Chip size="small" label={group.bars.length} sx={{ height: 20, fontWeight: 800 }} />
              </Box>
              <Box sx={{ position: 'relative', minWidth: LABEL_WIDTH + 640 }}>
                {todayPct != null ? (
                  <Box
                    sx={{
                      position: 'absolute',
                      left: `calc(${LABEL_WIDTH}px + (100% - ${LABEL_WIDTH}px) * ${todayPct / 100})`,
                      top: 0,
                      bottom: 0,
                      width: 2,
                      bgcolor: 'primary.main',
                      opacity: 0.25,
                      pointerEvents: 'none',
                      zIndex: 1,
                    }}
                  />
                ) : null}
                {group.bars.map((bar) => (
                  <GanttRow
                    key={bar.project_id}
                    bar={bar}
                    windowStart={windowStart}
                    totalDays={totalDays}
                    onOpen={() => navigateWithBack(navigate, `/projects/${bar.project_id}?tab=milestones`)}
                  />
                ))}
              </Box>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
