import { Box, Stack, Tooltip, Typography } from '@mui/material';
import type { DashboardCustomerWorkloadRow, DashboardProjectStageRow } from '../../types';
import { PROJECT_STAGE_LABELS } from '../../types/common';
import { chartTheme } from '../../theme/chartTheme';
import { formatNumber } from '../../utils/format';

function truncateLabel(value: string, max = 18): string {
  const trimmed = value.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1)}…`;
}

function DonutRing({
  segments,
  total,
  centerLabel,
  size = 148,
}: {
  segments: Array<{ id: string; value: number; color: string; label: string }>;
  total: number;
  centerLabel: string;
  size?: number;
}) {
  const stroke = 14;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <Box sx={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={chartTheme.surface.track}
          strokeWidth={stroke}
        />
        {segments.map((segment) => {
          const share = total > 0 ? segment.value / total : 0;
          const length = share * circumference;
          const dashOffset = -offset;
          offset += length;
          return (
            <circle
              key={segment.id}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={segment.color}
              strokeWidth={stroke}
              strokeDasharray={`${length} ${circumference - length}`}
              strokeDashoffset={dashOffset}
              strokeLinecap="butt"
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            />
          );
        })}
      </svg>
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          display: 'grid',
          placeItems: 'center',
          textAlign: 'center',
          pointerEvents: 'none',
        }}
      >
        <Box>
          <Typography
            sx={{
              fontSize: '1.5rem',
              fontWeight: 700,
              letterSpacing: '-0.03em',
              color: chartTheme.ink.primary,
              lineHeight: 1,
            }}
          >
            {total}
          </Typography>
          <Typography
            sx={{
              mt: 0.35,
              fontSize: '0.65rem',
              fontWeight: 600,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: chartTheme.ink.tertiary,
            }}
          >
            {centerLabel}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

function LegendList({
  items,
}: {
  items: Array<{ id: string; label: string; value: number; color: string; total: number }>;
}) {
  return (
    <Stack spacing={1.25} sx={{ flex: 1, minWidth: 0, justifyContent: 'center' }}>
      {items.map((item) => {
        const pct = item.total > 0 ? Math.round((item.value / item.total) * 100) : 0;
        return (
          <Box key={item.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                bgcolor: item.color,
                flexShrink: 0,
              }}
            />
            <Typography
              sx={{
                flex: 1,
                minWidth: 0,
                fontSize: '0.8125rem',
                fontWeight: 500,
                color: chartTheme.ink.secondary,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {item.label}
            </Typography>
            <Typography
              sx={{
                fontSize: '0.8125rem',
                fontWeight: 700,
                color: chartTheme.ink.primary,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {item.value}
            </Typography>
            <Typography
              sx={{
                width: 36,
                textAlign: 'right',
                fontSize: '0.75rem',
                fontWeight: 500,
                color: chartTheme.ink.tertiary,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {pct}%
            </Typography>
          </Box>
        );
      })}
    </Stack>
  );
}

interface ProjectStageChartProps {
  rows: DashboardProjectStageRow[];
  height?: number;
}

export function ProjectStageChart({ rows }: ProjectStageChartProps) {
  if (!rows.length) return null;

  const order = ['preliminary', 'intermediate', 'final'] as const;
  const sorted = [...rows].sort(
    (a, b) => order.indexOf(a.project_stage as (typeof order)[number]) - order.indexOf(b.project_stage as (typeof order)[number]),
  );

  const segments = sorted.map((row) => ({
    id: row.project_stage,
    value: row.project_count,
    label: PROJECT_STAGE_LABELS[row.project_stage],
    color:
      chartTheme.stage[row.project_stage as keyof typeof chartTheme.stage] ??
      chartTheme.ink.tertiary,
  }));
  const total = segments.reduce((sum, item) => sum + item.value, 0);

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5, minHeight: 180 }}>
      <DonutRing segments={segments} total={total} centerLabel="Active" />
      <LegendList items={segments.map((s) => ({ ...s, total }))} />
    </Box>
  );
}

interface ProjectHealthChartProps {
  green: number;
  yellow: number;
  red: number;
  grey?: number;
  height?: number;
}

export function ProjectHealthChart({
  green,
  yellow,
  red,
  grey = 0,
}: ProjectHealthChartProps) {
  const segments = [
    { id: 'green', value: green, label: 'On track', color: chartTheme.health.green },
    { id: 'yellow', value: yellow, label: 'At risk', color: chartTheme.health.yellow },
    { id: 'red', value: red, label: 'Critical', color: chartTheme.health.red },
    { id: 'grey', value: grey, label: 'Unrated', color: chartTheme.health.grey },
  ].filter((item) => item.value > 0);

  if (!segments.length) return null;

  const total = segments.reduce((sum, item) => sum + item.value, 0);

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5, minHeight: 180 }}>
      <DonutRing segments={segments} total={total} centerLabel="Projects" />
      <LegendList items={segments.map((s) => ({ ...s, total }))} />
    </Box>
  );
}

interface CustomerWorkloadChartProps {
  rows: DashboardCustomerWorkloadRow[];
  height?: number;
  limit?: number;
}

export function CustomerWorkloadChart({
  rows,
  limit = 5,
}: CustomerWorkloadChartProps) {
  const top = [...rows]
    .sort((a, b) => b.actual_hours - a.actual_hours)
    .slice(0, limit);

  if (!top.length) return null;

  const maxHours = Math.max(...top.map((row) => row.actual_hours), 1);

  return (
    <Stack spacing={1.75} sx={{ py: 0.5 }}>
      {top.map((row, index) => {
        const widthPct = Math.max(6, (row.actual_hours / maxHours) * 100);
        const color =
          chartTheme.workload[
            Math.min(index, chartTheme.workload.length - 1)
          ];
        return (
          <Tooltip
            key={row.customer_id}
            title={`${row.customer_name} · ${formatNumber(row.actual_hours, 1)}h · ${row.active_tools} tools`}
          >
            <Box>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  gap: 1,
                  mb: 0.75,
                }}
              >
                <Typography
                  sx={{
                    fontSize: '0.8125rem',
                    fontWeight: 600,
                    color: chartTheme.ink.primary,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {truncateLabel(row.customer_name, 22)}
                </Typography>
                <Typography
                  sx={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: chartTheme.ink.secondary,
                    fontVariantNumeric: 'tabular-nums',
                    flexShrink: 0,
                  }}
                >
                  {formatNumber(row.actual_hours, 0)}h
                </Typography>
              </Box>
              <Box
                sx={{
                  height: 8,
                  borderRadius: 999,
                  bgcolor: chartTheme.surface.track,
                  overflow: 'hidden',
                }}
              >
                <Box
                  sx={{
                    width: `${widthPct}%`,
                    height: '100%',
                    borderRadius: 999,
                    bgcolor: color,
                    transition: 'width 0.35s ease',
                  }}
                />
              </Box>
            </Box>
          </Tooltip>
        );
      })}
    </Stack>
  );
}

interface HoursSummaryChartProps {
  billableHours: number | string;
  nonBillableHours: number | string;
  npHours: number | string;
  height?: number;
}

function toHours(value: number | string | null | undefined): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function hoursPct(value: number, total: number): number {
  if (total <= 0) return 0;
  const pct = Math.round((value / total) * 100);
  return Number.isFinite(pct) ? pct : 0;
}

export function HoursSummaryChart({
  billableHours,
  nonBillableHours,
  npHours,
}: HoursSummaryChartProps) {
  const data = [
    {
      label: 'Billable',
      value: toHours(billableHours),
      color: chartTheme.hours.billable,
      soft: chartTheme.hours.billableSoft,
    },
    {
      label: 'Non-billable',
      value: toHours(nonBillableHours),
      color: chartTheme.hours.nonBillable,
      soft: chartTheme.hours.nonBillableSoft,
    },
    {
      label: 'NP',
      value: toHours(npHours),
      color: chartTheme.hours.np,
      soft: chartTheme.hours.npSoft,
    },
  ];

  const total = data.reduce((sum, item) => sum + item.value, 0);
  if (total <= 0) return null;

  return (
    <Stack spacing={2.25} sx={{ py: 0.5 }}>
      <Box>
        <Typography
          sx={{
            fontSize: '0.65rem',
            fontWeight: 600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: chartTheme.ink.tertiary,
            mb: 1,
          }}
        >
          Share of total hours
        </Typography>
        <Box
          sx={{
            display: 'flex',
            height: 12,
            borderRadius: 999,
            overflow: 'hidden',
            bgcolor: chartTheme.surface.track,
          }}
        >
          {data.map((item) => {
            const pct = hoursPct(item.value, total);
            if (pct <= 0 && item.value <= 0) return null;
            const barPct = total > 0 ? (item.value / total) * 100 : 0;
            if (barPct <= 0) return null;
            return (
              <Tooltip
                key={item.label}
                title={`${item.label}: ${formatNumber(item.value, 1)}h (${pct}%)`}
              >
                <Box
                  sx={{
                    width: `${barPct}%`,
                    bgcolor: item.color,
                    minWidth: barPct > 0 ? 4 : 0,
                    transition: 'width 0.35s ease',
                  }}
                />
              </Tooltip>
            );
          })}
        </Box>
      </Box>

      <Stack spacing={1.25}>
        {data.map((item) => {
          const pct = hoursPct(item.value, total);
          return (
            <Box
              key={item.label}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                px: 1.5,
                py: 1.25,
                borderRadius: 2,
                bgcolor: item.soft,
              }}
            >
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  bgcolor: item.color,
                  flexShrink: 0,
                }}
              />
              <Typography
                sx={{
                  flex: 1,
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  color: chartTheme.ink.primary,
                }}
              >
                {item.label}
              </Typography>
              <Typography
                sx={{
                  fontSize: '0.8125rem',
                  fontWeight: 700,
                  color: chartTheme.ink.primary,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatNumber(item.value, 0)}h
              </Typography>
              <Typography
                sx={{
                  width: 40,
                  textAlign: 'right',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: chartTheme.ink.secondary,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {pct}%
              </Typography>
            </Box>
          );
        })}
      </Stack>
    </Stack>
  );
}
