import { Box, Stack, Tooltip, Typography } from '@mui/material';
import type { DashboardDesignerAvailabilityRow } from '../../types';
import { chartTheme } from '../../theme/chartTheme';

function utilizationFromStatus(row: DashboardDesignerAvailabilityRow): number {
  switch (row.status) {
    case 'working':
      return 92;
    case 'on_hold':
      return 68;
    case 'leave':
      return 0;
    case 'available':
    default:
      return row.current_tool_number ? 55 : 28;
  }
}

function barColor(value: number): string {
  if (value >= 90) return chartTheme.utilization.high;
  if (value >= 75) return chartTheme.utilization.medium;
  return chartTheme.utilization.low;
}

function statusCaption(row: DashboardDesignerAvailabilityRow): string {
  if (row.status === 'working' && row.current_tool_number) {
    return row.current_tool_number;
  }
  if (row.status === 'on_hold') return 'On hold';
  if (row.status === 'leave') return 'Leave';
  return 'Open';
}

interface DesignerUtilizationListProps {
  rows: DashboardDesignerAvailabilityRow[];
  limit?: number;
}

export function DesignerUtilizationList({ rows, limit = 5 }: DesignerUtilizationListProps) {
  if (!rows.length) return null;

  const ranked = [...rows]
    .map((row) => ({ row, value: utilizationFromStatus(row) }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit);

  return (
    <Stack spacing={1.75} sx={{ height: '100%', minHeight: 0, py: 0.25, overflowY: 'auto' }}>
      {ranked.map(({ row, value }) => {
        const color = barColor(value);
        return (
          <Box key={row.user_id}>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                gap: 1,
                mb: 0.75,
              }}
            >
              <Tooltip title={row.designer_name}>
                <Typography
                  sx={{
                    fontSize: '0.8125rem',
                    fontWeight: 600,
                    color: chartTheme.ink.primary,
                    maxWidth: '58%',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {row.designer_name}
                </Typography>
              </Tooltip>
              <Typography
                sx={{
                  fontSize: '0.7rem',
                  fontWeight: 500,
                  color: chartTheme.ink.tertiary,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {statusCaption(row)}
              </Typography>
              <Typography
                sx={{
                  fontSize: '0.8125rem',
                  fontWeight: 700,
                  color,
                  fontVariantNumeric: 'tabular-nums',
                  flexShrink: 0,
                }}
              >
                {value}%
              </Typography>
            </Box>
            <Box
              sx={{
                height: 6,
                borderRadius: 999,
                bgcolor: chartTheme.utilization.track,
                overflow: 'hidden',
              }}
            >
              <Box
                sx={{
                  width: `${Math.min(100, value)}%`,
                  height: '100%',
                  borderRadius: 999,
                  bgcolor: color,
                  opacity: 0.9,
                  transition: 'width 0.35s ease',
                }}
              />
            </Box>
          </Box>
        );
      })}
      <Box
        sx={{
          display: 'flex',
          gap: 2,
          pt: 0.5,
          borderTop: `1px solid ${chartTheme.surface.hairline}`,
        }}
      >
        {[
          { label: 'Capacity', color: chartTheme.utilization.low },
          { label: 'Busy', color: chartTheme.utilization.medium },
          { label: 'Overload', color: chartTheme.utilization.high },
        ].map((item) => (
          <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: item.color }} />
            <Typography
              sx={{
                fontSize: '0.65rem',
                fontWeight: 600,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                color: chartTheme.ink.tertiary,
              }}
            >
              {item.label}
            </Typography>
          </Box>
        ))}
      </Box>
    </Stack>
  );
}
