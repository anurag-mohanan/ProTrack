import { Box, Stack, Tooltip, Typography } from '@mui/material';
import type { DashboardDesignerAvailabilityRow } from '../../types';
import { UtilizationBar } from '../ui/design-system/UtilizationBar';
import { designTokens } from '../../theme/designTokens';

/** Status-derived loading estimate until live utilization hours are wired. */
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

function statusCaption(row: DashboardDesignerAvailabilityRow): string {
  if (row.status === 'working' && row.current_tool_number) {
    return `On ${row.current_tool_number}`;
  }
  if (row.status === 'on_hold') return 'Project on hold';
  if (row.status === 'leave') return 'On leave';
  return 'Available capacity';
}

interface DesignerUtilizationListProps {
  rows: DashboardDesignerAvailabilityRow[];
  limit?: number;
}

export function DesignerUtilizationList({ rows, limit = 6 }: DesignerUtilizationListProps) {
  if (!rows.length) {
    return null;
  }

  const ranked = [...rows]
    .map((row) => ({ row, value: utilizationFromStatus(row) }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit);

  return (
    <Stack spacing={1.5}>
      {ranked.map(({ row, value }) => (
        <Box key={row.user_id}>
          <Stack
            direction="row"
            sx={{ mb: 0.5, justifyContent: 'space-between', alignItems: 'baseline' }}
          >
            <Tooltip title={row.designer_name}>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 700,
                  maxWidth: '70%',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {row.designer_name}
              </Typography>
            </Tooltip>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
              {statusCaption(row)}
            </Typography>
          </Stack>
          <UtilizationBar label="" value={value} hideLabel />
        </Box>
      ))}
      <Typography variant="caption" color="text.secondary" sx={{ pt: 0.25 }}>
        <Box
          component="span"
          sx={{
            display: 'inline-block',
            width: 8,
            height: 8,
            borderRadius: '50%',
            bgcolor: designTokens.utilization.high,
            mr: 0.75,
          }}
        />
        ≥90% overloaded ·{' '}
        <Box
          component="span"
          sx={{
            display: 'inline-block',
            width: 8,
            height: 8,
            borderRadius: '50%',
            bgcolor: designTokens.utilization.medium,
            mx: 0.5,
          }}
        />
        75–89% busy ·{' '}
        <Box
          component="span"
          sx={{
            display: 'inline-block',
            width: 8,
            height: 8,
            borderRadius: '50%',
            bgcolor: designTokens.utilization.low,
            mx: 0.5,
          }}
        />
        &lt;75% capacity
      </Typography>
    </Stack>
  );
}
