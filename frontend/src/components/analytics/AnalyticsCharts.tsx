import { Box } from '@mui/material';
import { BarChart } from '@mui/x-charts/BarChart';
import { LineChart } from '@mui/x-charts/LineChart';
import { PieChart } from '@mui/x-charts/PieChart';
import { designTokens } from '../../theme/designTokens';

const CHART_COLORS = [
  designTokens.semantic.primary,
  designTokens.semantic.success,
  designTokens.semantic.warning,
  designTokens.semantic.danger,
  '#8b5cf6',
  '#0ea5e9',
  designTokens.semantic.neutral,
];

interface DonutChartProps {
  data: Array<{ id: string; label: string; value: number; color?: string }>;
  height?: number;
}

export function AnalyticsDonutChart({ data, height = 260 }: DonutChartProps) {
  const filtered = data.filter((d) => d.value > 0);
  if (!filtered.length) return null;

  return (
    <Box sx={{ width: '100%', height }}>
      <PieChart
        series={[
          {
            data: filtered.map((item, index) => ({
              id: item.id,
              value: item.value,
              label: item.label,
              color: item.color ?? CHART_COLORS[index % CHART_COLORS.length],
            })),
            innerRadius: 48,
            outerRadius: 90,
            paddingAngle: 2,
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

interface BarSeriesChartProps {
  categories: string[];
  series: Array<{ label: string; data: number[]; color?: string; stack?: string }>;
  height?: number;
  horizontal?: boolean;
}

export function AnalyticsBarChart({
  categories,
  series,
  height = 280,
  horizontal = false,
}: BarSeriesChartProps) {
  if (!categories.length || !series.length) return null;

  return (
    <Box sx={{ width: '100%', height }}>
      <BarChart
        height={height}
        layout={horizontal ? 'horizontal' : 'vertical'}
        xAxis={horizontal ? undefined : [{ scaleType: 'band', data: categories }]}
        yAxis={horizontal ? [{ scaleType: 'band', data: categories }] : undefined}
        series={series.map((s, index) => ({
          data: s.data,
          label: s.label,
          stack: s.stack,
          color: s.color ?? CHART_COLORS[index % CHART_COLORS.length],
        }))}
        margin={{ left: horizontal ? 100 : 48, right: 16, top: 16, bottom: 40 }}
      />
    </Box>
  );
}

interface LineTrendChartProps {
  labels: string[];
  values: number[];
  height?: number;
  label?: string;
}

export function AnalyticsLineChart({ labels, values, height = 260, label = 'Trend' }: LineTrendChartProps) {
  if (!labels.length) return null;

  return (
    <Box sx={{ width: '100%', height }}>
      <LineChart
        height={height}
        xAxis={[{ scaleType: 'point', data: labels }]}
        series={[{ data: values, label, color: designTokens.semantic.primary, area: true }]}
        margin={{ left: 48, right: 16, top: 16, bottom: 40 }}
      />
    </Box>
  );
}
