import { Box, Tooltip, Typography } from '@mui/material';
import { designTokens } from '../../theme/designTokens';
import { formatNumber } from '../../utils/format';

export interface HeatmapCell {
  rowId: string;
  rowLabel: string;
  columnId: string;
  columnLabel: string;
  value: number;
  maxValue?: number;
}

interface WorkloadHeatmapProps {
  rows: string[];
  columns: string[];
  cells: HeatmapCell[];
  rowLabels?: Record<string, string>;
  columnLabels?: Record<string, string>;
}

function cellColor(value: number, max: number): string {
  if (max <= 0 || value <= 0) return designTokens.semantic.neutralSoft;
  const ratio = value / max;
  if (ratio >= 0.9) return `${designTokens.utilization.high}33`;
  if (ratio >= 0.7) return `${designTokens.utilization.medium}33`;
  return `${designTokens.utilization.low}33`;
}

function cellBorder(value: number, max: number): string {
  if (max <= 0 || value <= 0) return 'divider';
  const ratio = value / max;
  if (ratio >= 0.9) return designTokens.utilization.high;
  if (ratio >= 0.7) return designTokens.utilization.medium;
  return designTokens.utilization.low;
}

export function WorkloadHeatmap({ rows, columns, cells, rowLabels, columnLabels }: WorkloadHeatmapProps) {
  const max = Math.max(...cells.map((c) => c.value), 1);
  const lookup = new Map(cells.map((c) => [`${c.rowId}:${c.columnId}`, c]));

  return (
    <Box sx={{ overflow: 'auto' }}>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: `160px repeat(${columns.length}, minmax(72px, 1fr))`,
          gap: 0.5,
          minWidth: 160 + columns.length * 72,
        }}
      >
        <Box />
        {columns.map((col) => (
          <Typography
            key={col}
            variant="caption"
            sx={{ fontWeight: 700, textAlign: 'center', px: 0.5, py: 1 }}
          >
            {columnLabels?.[col] ?? col}
          </Typography>
        ))}
        {rows.map((row) => (
          <Box key={row} sx={{ display: 'contents' }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                px: 1,
                py: 1.25,
                display: 'flex',
                alignItems: 'center',
                bgcolor: designTokens.semantic.neutralSoft,
                borderRadius: `${designTokens.radius.sm}px`,
              }}
            >
              {rowLabels?.[row] ?? row}
            </Typography>
            {columns.map((col) => {
              const cell = lookup.get(`${row}:${col}`);
              const value = cell?.value ?? 0;
              return (
                <Tooltip
                  key={`${row}-${col}`}
                  title={`${rowLabels?.[row] ?? row} · ${columnLabels?.[col] ?? col}: ${formatNumber(value, 1)}h`}
                >
                  <Box
                    sx={{
                      minHeight: 44,
                      display: 'grid',
                      placeItems: 'center',
                      borderRadius: `${designTokens.radius.sm}px`,
                      bgcolor: cellColor(value, max),
                      border: '1px solid',
                      borderColor: cellBorder(value, max),
                      fontWeight: 700,
                      fontSize: '0.75rem',
                      transition: `transform ${designTokens.motion.fast}`,
                      '&:hover': { transform: 'scale(1.04)' },
                    }}
                  >
                    {value > 0 ? formatNumber(value, 0) : '—'}
                  </Box>
                </Tooltip>
              );
            })}
          </Box>
        ))}
      </Box>
    </Box>
  );
}
