import { Box } from '@mui/material';
import { BarChart } from '@mui/x-charts/BarChart';
import { PieChart } from '@mui/x-charts/PieChart';
import type { DashboardCustomerWorkloadRow } from '../../types';
import type { DashboardProjectStageRow } from '../../types';
import { PROJECT_STAGE_LABELS } from '../../types/common';
import { designTokens } from '../../theme/designTokens';

const STAGE_CHART_COLORS = ['#6366f1', '#2563eb', '#0ea5e9', '#8b5cf6', '#14b8a6', '#64748b'];

interface ProjectStageChartProps {
  rows: DashboardProjectStageRow[];
  height?: number;
}

export function ProjectStageChart({ rows, height = 260 }: ProjectStageChartProps) {
  if (!rows.length) return null;

  const data = rows.map((row, index) => ({
    id: row.project_stage,
    value: row.project_count,
    label: PROJECT_STAGE_LABELS[row.project_stage],
    color: STAGE_CHART_COLORS[index % STAGE_CHART_COLORS.length],
  }));

  return (
    <Box sx={{ width: '100%', height }}>
      <PieChart
        series={[
          {
            data,
            innerRadius: 52,
            outerRadius: 96,
            paddingAngle: 2,
            cornerRadius: 4,
            highlightScope: { fade: 'global', highlight: 'item' },
          },
        ]}
        height={height}
        margin={{ top: 8, bottom: 8, left: 8, right: 8 }}
        slotProps={{
          legend: {
            direction: 'vertical',
            position: { vertical: 'middle', horizontal: 'end' },
          },
        }}
        sx={{ '& .MuiChartsLegend-label': { fontSize: 12, fontWeight: 600 } }}
      />
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
    { id: 'grey', value: grey, label: 'Grey', color: designTokens.health.grey.main },
  ].filter((item) => item.value > 0);

  if (!data.length) return null;

  return (
    <Box sx={{ width: '100%', height }}>
      <PieChart
        series={[
          {
            data,
            innerRadius: 40,
            outerRadius: 80,
            paddingAngle: 3,
            cornerRadius: 4,
          },
        ]}
        height={height}
        margin={{ top: 8, bottom: 8, left: 8, right: 120 }}
        slotProps={{
          legend: { direction: 'vertical', position: { vertical: 'middle', horizontal: 'end' } },
        }}
      />
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

  return (
    <Box sx={{ width: '100%', height }}>
      <BarChart
        height={height}
        layout="horizontal"
        yAxis={[{ scaleType: 'band', data: top.map((r) => r.customer_name) }]}
        series={[
          {
            data: top.map((r) => r.actual_hours),
            label: 'Hours Logged',
            color: designTokens.semantic.primary,
          },
        ]}
        margin={{ left: 100, right: 16, top: 8, bottom: 32 }}
        sx={{ '& .MuiChartsAxis-tickLabel': { fontSize: 11, fontWeight: 600 } }}
      />
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
  ].filter((item) => item.value > 0);

  if (!data.length) return null;

  return (
    <Box sx={{ width: '100%', height }}>
      <BarChart
        height={height}
        xAxis={[{ scaleType: 'band', data: data.map((d) => d.label) }]}
        series={[{ data: data.map((d) => d.value) }]}
        colors={data.map((d) => d.color)}
        margin={{ left: 48, right: 16, top: 8, bottom: 40 }}
      />
    </Box>
  );
}
