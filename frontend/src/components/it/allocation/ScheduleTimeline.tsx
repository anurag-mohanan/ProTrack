import { Box, Stack, Tooltip, Typography } from '@mui/material';
import type { ScheduleBlock } from '../../../types/itAllocation';

const DAY = 24 * 60;

function minutes(value: string): number {
  const [h, m] = value.split(':').map(Number);
  return h * 60 + (m || 0);
}

function occupantLabel(block: ScheduleBlock): string {
  if (!block.occupants.length) return 'Available';
  return block.occupants
    .map((o) => `${o.user_name || (o.kind === 'reservation' ? 'Reserved' : 'Assigned')}${o.legacy ? ' (legacy)' : ''}`)
    .join(', ');
}

type Props = { blocks: ScheduleBlock[]; capacityLabel?: string };

/** 24-hour occupancy bar plus a readable block list (e.g. 06:00–14:00 Anurag · 22:00–06:00 Available). */
export function ScheduleTimeline({ blocks, capacityLabel }: Props) {
  if (!blocks.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No schedule for this date.
      </Typography>
    );
  }
  return (
    <Stack spacing={1}>
      <Box sx={{ display: 'flex', height: 22, borderRadius: 1, overflow: 'hidden', border: 1, borderColor: 'divider' }}>
        {blocks.map((b) => {
          const width = ((minutes(b.end) || DAY) - minutes(b.start)) / DAY;
          return (
            <Tooltip key={`${b.start}-${b.end}`} title={`${b.start}–${b.end} · ${occupantLabel(b)}`}>
              <Box
                sx={{
                  width: `${width * 100}%`,
                  bgcolor: b.available ? (b.occupants.length ? 'warning.light' : 'success.light') : 'error.light',
                  borderRight: 1,
                  borderColor: 'background.paper',
                }}
              />
            </Tooltip>
          );
        })}
      </Box>
      <Stack spacing={0.25}>
        {blocks.map((b) => (
          <Typography key={`row-${b.start}-${b.end}`} variant="body2">
            <Box component="span" sx={{ fontFamily: 'monospace', mr: 1 }}>
              {b.start}–{b.end}
            </Box>
            {occupantLabel(b)}
            {b.remaining_capacity !== null && b.occupants.length > 0 ? (
              <Typography component="span" variant="caption" color="text.secondary">
                {' '}
                · {capacityLabel || 'Remaining'}: {Math.max(0, b.remaining_capacity)}
              </Typography>
            ) : null}
          </Typography>
        ))}
      </Stack>
    </Stack>
  );
}
