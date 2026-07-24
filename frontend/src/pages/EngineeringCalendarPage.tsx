import { useCallback, useMemo, useRef, useState } from 'react';
import { Box, Chip, Collapse, Stack, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { fetchProjectTimeline, type ProjectTimelineBar } from '../api/calendar';
import { designTokens } from '../theme/designTokens';
import { navigateWithBack } from '../hooks/useBackNavigation';

const DAY_MS = 24 * 60 * 60 * 1000;
const LABEL_WIDTH = 220;
const ROW_HEIGHT = 36;
const HEADER_HEIGHT = 40;
const MONTH_COL_MIN_PX = 72;

const ACTIVE_STATUSES = new Set([
  'planning',
  'currently_being_worked_on',
  'on_hold',
]);

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

function isCompletedBar(bar: ProjectTimelineBar): boolean {
  return bar.execution_status === 'completed' || bar.progress_percent >= 100;
}

function isActiveBar(bar: ProjectTimelineBar): boolean {
  if (isCompletedBar(bar)) return false;
  if (bar.execution_status === 'cancelled') return false;
  return ACTIVE_STATUSES.has(bar.execution_status) || !bar.execution_status;
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

/** Month ticks with enough horizontal spacing so labels never overlap. */
function monthTicks(
  windowStart: Date,
  totalDays: number,
  timelineWidthPx: number,
): { leftPct: number; label: string }[] {
  const raw: { leftPct: number; label: string; dayIndex: number }[] = [];
  for (let i = 0; i <= totalDays; i += 1) {
    const day = addDays(windowStart, i);
    if (day.getDate() === 1 || i === 0) {
      raw.push({
        dayIndex: i,
        leftPct: (i / Math.max(totalDays, 1)) * 100,
        label: day.toLocaleDateString(undefined, { month: 'short', year: '2-digit' }),
      });
    }
  }
  const minGapPct = (MONTH_COL_MIN_PX / Math.max(timelineWidthPx, 1)) * 100;
  const filtered: { leftPct: number; label: string }[] = [];
  let lastPct = -Infinity;
  for (const tick of raw) {
    if (tick.leftPct - lastPct < minGapPct && filtered.length > 0) {
      continue;
    }
    filtered.push({ leftPct: tick.leftPct, label: tick.label });
    lastPct = tick.leftPct;
  }
  return filtered;
}

function GanttRow({
  bar,
  windowStart,
  totalDays,
  timelineWidthPx,
  onOpen,
}: {
  bar: ProjectTimelineBar;
  windowStart: Date;
  totalDays: number;
  timelineWidthPx: number;
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
        gridTemplateColumns: `${LABEL_WIDTH}px ${timelineWidthPx}px`,
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
          zIndex: 2,
          bgcolor: 'background.paper',
          borderRight: '1px solid',
          borderColor: 'divider',
          boxShadow: '4px 0 8px -4px rgba(15, 23, 42, 0.12)',
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
      <Box sx={{ position: 'relative', width: timelineWidthPx }}>
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
            sx={{
              color: '#fff',
              fontWeight: 800,
              fontSize: '0.65rem',
              textShadow: '0 1px 1px rgba(0,0,0,0.25)',
            }}
            noWrap
          >
            {missingDue ? 'TBD' : `${Math.round(bar.progress_percent)}%`}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

function TeamSection({
  group,
  windowStart,
  totalDays,
  timelineWidthPx,
  todayPct,
  onOpen,
}: {
  group: TeamGroup;
  windowStart: Date;
  totalDays: number;
  timelineWidthPx: number;
  todayPct: number | null;
  onOpen: (projectId: string) => void;
}) {
  return (
    <Box>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: `${LABEL_WIDTH}px ${timelineWidthPx}px`,
          bgcolor: 'action.hover',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Box
          sx={{
            px: 1.25,
            py: 0.75,
            position: 'sticky',
            left: 0,
            zIndex: 2,
            bgcolor: 'action.hover',
            borderRight: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            boxShadow: '4px 0 8px -4px rgba(15, 23, 42, 0.1)',
          }}
        >
          <Typography sx={{ fontWeight: 800, fontSize: '0.85rem' }} noWrap>
            {group.title}
          </Typography>
          <Chip size="small" label={group.bars.length} sx={{ height: 20, fontWeight: 800 }} />
        </Box>
        <Box sx={{ position: 'relative', width: timelineWidthPx }} />
      </Box>
      <Box sx={{ position: 'relative', width: LABEL_WIDTH + timelineWidthPx }}>
        {todayPct != null ? (
          <Box
            sx={{
              position: 'absolute',
              left: LABEL_WIDTH + (timelineWidthPx * todayPct) / 100,
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
            timelineWidthPx={timelineWidthPx}
            onOpen={() => onOpen(bar.project_id)}
          />
        ))}
      </Box>
    </Box>
  );
}

export default function EngineeringCalendarPage() {
  const navigate = useNavigate();
  const window = useMemo(() => defaultWindow(), []);
  const headerScrollRef = useRef<HTMLDivElement | null>(null);
  const bodyScrollRef = useRef<HTMLDivElement | null>(null);
  const syncingRef = useRef(false);
  const [completedOpen, setCompletedOpen] = useState(false);

  const query = useQuery({
    queryKey: ['project-timeline', window.from, window.to],
    queryFn: () => fetchProjectTimeline({ from: window.from, to: window.to }),
  });

  const windowStart = useMemo(() => parseDay(window.from), [window.from]);
  const windowEnd = useMemo(() => parseDay(window.to), [window.to]);
  const totalDays = Math.max(daysBetween(windowStart, windowEnd), 1);
  const monthCount = Math.max(Math.ceil(totalDays / 30), 1);
  const timelineWidthPx = Math.max(640, monthCount * MONTH_COL_MIN_PX);
  const ticks = useMemo(
    () => monthTicks(windowStart, totalDays, timelineWidthPx),
    [windowStart, totalDays, timelineWidthPx],
  );

  const { activeBars, completedBars } = useMemo(() => {
    const all = query.data ?? [];
    const active: ProjectTimelineBar[] = [];
    const completed: ProjectTimelineBar[] = [];
    for (const bar of all) {
      if (isActiveBar(bar)) active.push(bar);
      else if (isCompletedBar(bar)) completed.push(bar);
      // cancelled omitted from calendar
    }
    return { activeBars: active, completedBars: completed };
  }, [query.data]);

  const activeGroups = useMemo(() => groupByTeam(activeBars), [activeBars]);
  const completedGroups = useMemo(() => groupByTeam(completedBars), [completedBars]);

  const todayOffset = daysBetween(windowStart, new Date(new Date().setHours(0, 0, 0, 0)));
  const todayPct =
    todayOffset >= 0 && todayOffset <= totalDays ? (todayOffset / totalDays) * 100 : null;

  const syncScroll = useCallback((source: 'header' | 'body') => {
    if (syncingRef.current) return;
    const header = headerScrollRef.current;
    const body = bodyScrollRef.current;
    if (!header || !body) return;
    syncingRef.current = true;
    if (source === 'header') {
      body.scrollLeft = header.scrollLeft;
    } else {
      header.scrollLeft = body.scrollLeft;
    }
    requestAnimationFrame(() => {
      syncingRef.current = false;
    });
  }, []);

  const openProject = useCallback(
    (projectId: string) => {
      navigateWithBack(navigate, `/projects/${projectId}?tab=milestones`);
    },
    [navigate],
  );

  if (query.isLoading) return <LoadingState message="Loading project timeline…" />;

  const totalWidth = LABEL_WIDTH + timelineWidthPx;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, minHeight: 0 }}>
      <PageHeader
        title="Project Calendar"
        subtitle="Active project timeline from created date through due date"
      />

      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
        <Chip size="small" label="Green" sx={{ bgcolor: designTokens.health.green.soft, fontWeight: 700 }} />
        <Chip size="small" label="Yellow" sx={{ bgcolor: designTokens.health.yellow.soft, fontWeight: 700 }} />
        <Chip size="small" label="Red" sx={{ bgcolor: designTokens.health.red.soft, fontWeight: 700 }} />
        <Chip size="small" variant="outlined" label="On hold = muted" sx={{ fontWeight: 700 }} />
        <Chip size="small" variant="outlined" label="TBD = missing due date" sx={{ fontWeight: 700 }} />
        <Chip size="small" variant="outlined" label="Completed collapsed below" sx={{ fontWeight: 700 }} />
      </Stack>

      {!activeGroups.length && !completedGroups.length ? (
        <EmptyState title="No projects in range" description="Adjust the date window or create a project." />
      ) : (
        <Box
          sx={{
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            bgcolor: 'background.paper',
            display: 'flex',
            flexDirection: 'column',
            height: 'calc(100dvh - 220px)',
            minHeight: 320,
            overflow: 'hidden',
          }}
        >
          {/* Date / PROJECT header — outside vertical scroll so it never moves down */}
          <Box
            ref={headerScrollRef}
            onScroll={() => syncScroll('header')}
            sx={{
              flexShrink: 0,
              overflowX: 'auto',
              overflowY: 'hidden',
              borderBottom: '1px solid',
              borderColor: 'divider',
              bgcolor: 'background.paper',
              // Hide scrollbar on header; body scrollbar drives horizontal scroll feel
              scrollbarWidth: 'none',
              '&::-webkit-scrollbar': { display: 'none' },
            }}
          >
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: `${LABEL_WIDTH}px ${timelineWidthPx}px`,
                width: totalWidth,
                height: HEADER_HEIGHT,
              }}
            >
              <Box
                sx={{
                  px: 1,
                  display: 'flex',
                  alignItems: 'center',
                  position: 'sticky',
                  left: 0,
                  zIndex: 3,
                  bgcolor: 'background.paper',
                  borderRight: '1px solid',
                  borderColor: 'divider',
                  boxShadow: '4px 0 8px -4px rgba(15, 23, 42, 0.12)',
                }}
              >
                <Typography variant="caption" sx={{ fontWeight: 800, color: 'text.secondary' }}>
                  PROJECT
                </Typography>
              </Box>
              <Box sx={{ position: 'relative', width: timelineWidthPx, height: HEADER_HEIGHT }}>
                {ticks.map((tick) => (
                  <Typography
                    key={`${tick.label}-${tick.leftPct.toFixed(2)}`}
                    variant="caption"
                    sx={{
                      position: 'absolute',
                      left: `${tick.leftPct}%`,
                      top: 12,
                      pl: 0.5,
                      fontWeight: 800,
                      color: 'text.secondary',
                      whiteSpace: 'nowrap',
                      pointerEvents: 'none',
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
          </Box>

          {/* Body: vertical + horizontal scroll; PROJECT labels sticky left */}
          <Box
            ref={bodyScrollRef}
            onScroll={() => syncScroll('body')}
            sx={{
              flex: 1,
              minHeight: 0,
              overflow: 'auto',
            }}
          >
            {!activeGroups.length ? (
              <Box sx={{ p: 3 }}>
                <Typography color="text.secondary">No active projects in this window.</Typography>
              </Box>
            ) : (
              activeGroups.map((group) => (
                <TeamSection
                  key={group.key}
                  group={group}
                  windowStart={windowStart}
                  totalDays={totalDays}
                  timelineWidthPx={timelineWidthPx}
                  todayPct={todayPct}
                  onOpen={openProject}
                />
              ))
            )}

            {completedGroups.length > 0 ? (
              <Box sx={{ borderTop: '1px solid', borderColor: 'divider' }}>
                <Box
                  onClick={() => setCompletedOpen((open) => !open)}
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: `${LABEL_WIDTH}px ${timelineWidthPx}px`,
                    width: totalWidth,
                    cursor: 'pointer',
                    bgcolor: 'grey.50',
                    '&:hover': { bgcolor: 'action.hover' },
                  }}
                >
                  <Box
                    sx={{
                      px: 1.25,
                      py: 1,
                      position: 'sticky',
                      left: 0,
                      zIndex: 2,
                      bgcolor: 'grey.50',
                      borderRight: '1px solid',
                      borderColor: 'divider',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                    }}
                  >
                    {completedOpen ? (
                      <ExpandLessIcon fontSize="small" color="action" />
                    ) : (
                      <ExpandMoreIcon fontSize="small" color="action" />
                    )}
                    <Typography sx={{ fontWeight: 800, fontSize: '0.85rem' }}>
                      Completed
                    </Typography>
                    <Chip
                      size="small"
                      label={completedBars.length}
                      sx={{ height: 20, fontWeight: 800 }}
                    />
                  </Box>
                  <Box sx={{ width: timelineWidthPx }} />
                </Box>
                <Collapse in={completedOpen} unmountOnExit>
                  {completedGroups.map((group) => (
                    <TeamSection
                      key={`done-${group.key}`}
                      group={group}
                      windowStart={windowStart}
                      totalDays={totalDays}
                      timelineWidthPx={timelineWidthPx}
                      todayPct={todayPct}
                      onOpen={openProject}
                    />
                  ))}
                </Collapse>
              </Box>
            ) : null}
          </Box>
        </Box>
      )}
    </Box>
  );
}
