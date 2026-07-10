import { Box, Stack, Tooltip, Typography } from '@mui/material';
import { BarChart } from '@mui/x-charts/BarChart';
import { PieChart } from '@mui/x-charts/PieChart';
import type { DashboardCustomerWorkloadRow, DashboardProjectStageRow } from '../../types';
import { PROJECT_STAGE_LABELS } from '../../types/common';
import { designTokens } from '../../theme/designTokens';
import { formatNumber } from '../../utils/format';

const STAGE_CHART_COLORS: Record<string, string> = {
  preliminary: designTokens.stage.preliminary.main,
  intermediate: designTokens.stage.intermediate.main,
  final: designTokens.stage.final.main,
};

function truncateLabel(value: string, max = 14): string {
  const trimmed = value.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1)}…`;
}

function niceAxisMax(value: number): number {
  if (value <= 0) return 10;
  const padded = value * 1.12;
  const magnitude = 10 ** Math.floor(Math.log10(padded));
  const normalized = padded / magnitude;
  const nice =
    normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return nice * magnitude;
}

interface ProjectStageChartProps {
  rows: DashboardProjectStageRow[];
  height?: number;
}

export function ProjectStageChart({ rows, height = 260 }: ProjectStageChartProps) {
  if (!rows.length) return null;

  const data = rows.map((row) => ({
    id: row.project_stage,
    value: row.project_count,
    label: PROJECT_STAGE_LABELS[row.project_stage],
    color: STAGE_CHART_COLORS[row.project_stage] ?? designTokens.semantic.neutral,
  }));
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <Box sx={{ position: 'relative', width: '100%', height }}>
      <PieChart
        series={[
          {
            data,
            innerRadius: 54,
            outerRadius: 88,
            paddingAngle: 2,
            cornerRadius: 4,
            arcLabel: (item) => (item.value > 0 ? `${item.value}` : ''),
            arcLabelMinAngle: 18,
            highlightScope: { fade: 'global', highlight: 'item' },
            valueFormatter: (item) =>
              `${item.value} · ${total > 0 ? Math.round((item.value / total) * 100) : 0}%`,
          },
        ]}
        height={height}
        margin={{ top: 8, bottom: 8, left: 8, right: 110 }}
        slotProps={{
          legend: {
            direction: 'vertical',
            position: { vertical: 'middle', horizontal: 'end' },
          },
        }}
        sx={{
          '& .MuiChartsLegend-label': { fontSize: 12, fontWeight: 600 },
          '& .MuiPieArcLabel-root': { fontSize: 11, fontWeight: 700, fill: '#fff' },
        }}
      />
      <Box
        sx={{
          position: 'absolute',
          left: '28%',
          top: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center',
          pointerEvents: 'none',
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1.1 }}>
          {total}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
          Active
        </Typography>
      </Box>
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
  height = 220,
}: ProjectHealthChartProps) {
  const data = [
    { id: 'green', value: green, label: 'Green', color: designTokens.health.green.main },
    { id: 'yellow', value: yellow, label: 'Amber', color: designTokens.health.yellow.main },
    { id: 'red', value: red, label: 'Red', color: designTokens.health.red.main },
    { id: 'grey', value: grey, label: 'Unrated', color: designTokens.health.grey.main },
  ].filter((item) => item.value > 0);

  if (!data.length) return null;

  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <Box sx={{ position: 'relative', width: '100%', height }}>
      <PieChart
        series={[
          {
            data,
            innerRadius: 54,
            outerRadius: 88,
            paddingAngle: 3,
            cornerRadius: 4,
            arcLabel: (item) => (item.value > 0 ? `${item.value}` : ''),
            arcLabelMinAngle: 16,
            valueFormatter: (item) =>
              `${item.value} · ${total > 0 ? Math.round((item.value / total) * 100) : 0}%`,
          },
        ]}
        height={height}
        margin={{ top: 8, bottom: 8, left: 8, right: 110 }}
        slotProps={{
          legend: { direction: 'vertical', position: { vertical: 'middle', horizontal: 'end' } },
        }}
        sx={{
          '& .MuiChartsLegend-label': { fontSize: 12, fontWeight: 600 },
          '& .MuiPieArcLabel-root': { fontSize: 11, fontWeight: 700, fill: '#fff' },
        }}
      />
      <Box
        sx={{
          position: 'absolute',
          left: '28%',
          top: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center',
          pointerEvents: 'none',
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1.1 }}>
          {total}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
          Projects
        </Typography>
      </Box>
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
  height = 260,
  limit = 6,
}: CustomerWorkloadChartProps) {
  const top = [...rows]
    .sort((a, b) => b.actual_hours - a.actual_hours)
    .slice(0, limit);

  if (!top.length) return null;

  const maxHours = Math.max(...top.map((row) => row.actual_hours), 0);
  const labels = top.map((row) => truncateLabel(row.customer_name, 16));
  const fullNames = top.map((row) => row.customer_name);

  return (
    <Box sx={{ width: '100%', height }}>
      <BarChart
        height={height}
        layout="horizontal"
        yAxis={[
          {
            scaleType: 'band',
            data: labels,
            width: 112,
            tickLabelStyle: { fontSize: 11, fontWeight: 600 },
          },
        ]}
        xAxis={[
          {
            min: 0,
            max: niceAxisMax(maxHours),
            valueFormatter: (value: number | null) =>
              value == null ? '' : formatNumber(value, value >= 100 ? 0 : 1),
          },
        ]}
        series={[
          {
            data: top.map((row) => row.actual_hours),
            label: 'Hours logged',
            color: designTokens.semantic.primary,
            valueFormatter: (value, context) => {
              if (value == null) return '';
              const name = fullNames[context.dataIndex] ?? '';
              return `${formatNumber(value, 1)}h${name ? ` · ${name}` : ''}`;
            },
          },
        ]}
        grid={{ vertical: true }}
        margin={{ left: 8, right: 20, top: 12, bottom: 28 }}
        sx={{
          '& .MuiChartsAxis-tickLabel': { fontSize: 11, fontWeight: 600 },
          '& .MuiBarElement-root': { rx: 4 },
          '& .MuiChartsLegend-root': { display: 'none' },
        }}
      />
      <Stack direction="row" spacing={1} sx={{ mt: -0.5, flexWrap: 'wrap', gap: 0.5 }}>
        {top.map((row) => (
          <Tooltip key={row.customer_id} title={`${row.customer_name}: ${formatNumber(row.actual_hours, 1)}h · ${row.active_tools} tools`}>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
              {truncateLabel(row.customer_name, 10)} {formatNumber(row.actual_hours, 0)}h
            </Typography>
          </Tooltip>
        ))}
      </Stack>
    </Box>
  );
}

interface HoursSummaryChartProps {
  billableHours: number;
  nonBillableHours: number;
  npHours: number;
  height?: number;
}

export function HoursSummaryChart({
  billableHours,
  nonBillableHours,
  npHours,
  height = 220,
}: HoursSummaryChartProps) {
  const data = [
    { label: 'Billable', value: billableHours, color: designTokens.semantic.success },
    { label: 'Non-Billable', value: nonBillableHours, color: designTokens.semantic.primary },
    { label: 'NP Hours', value: npHours, color: designTokens.semantic.warning },
  ];

  const maxValue = Math.max(...data.map((item) => item.value), 0);
  if (maxValue <= 0) return null;

  return (
    <Box sx={{ width: '100%', height }}>
      <BarChart
        height={height}
        xAxis={[
          {
            scaleType: 'band',
            data: data.map((item) => item.label),
            tickLabelStyle: { fontSize: 11, fontWeight: 600 },
          },
        ]}
        yAxis={[
          {
            min: 0,
            max: niceAxisMax(maxValue),
            valueFormatter: (value: number | null) =>
              value == null ? '' : formatNumber(value, value >= 1000 ? 0 : 1),
          },
        ]}
        series={[
          {
            data: data.map((item) => item.value),
            label: 'Hours',
            valueFormatter: (value) => (value == null ? '' : `${formatNumber(value, 1)}h`),
          },
        ]}
        colors={data.map((item) => item.color)}
        grid={{ horizontal: true }}
        margin={{ left: 52, right: 12, top: 16, bottom: 36 }}
        sx={{
          '& .MuiBarElement-root': { rx: 4 },
          '& .MuiChartsLegend-root': { display: 'none' },
        }}
      />
      <Stack direction="row" spacing={2} sx={{ mt: -0.5, justifyContent: 'center' }}>
        {data.map((item) => (
          <Stack key={item.label} direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
            <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: item.color }} />
            <Typography variant="caption" sx={{ fontWeight: 700 }}>
              {item.label} {formatNumber(item.value, 0)}h
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Box>
  );
}
