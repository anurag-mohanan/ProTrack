import { Box, Stack, Typography } from '@mui/material';
import type {
  DashboardDesignerAvailabilityRow,
  DashboardDesignerAvailabilitySummary,
} from '../../types';
import { chartTheme } from '../../theme/chartTheme';

interface ResourceAvailabilityPanelProps {
  summary?: DashboardDesignerAvailabilitySummary;
  rows: DashboardDesignerAvailabilityRow[];
  limit?: number;
}

export function ResourceAvailabilityPanel({
  summary,
  rows,
  limit = 5,
}: ResourceAvailabilityPanelProps) {
  const openRows = rows.filter((row) => row.status === 'available').slice(0, limit);

  const totals = summary ?? {
    total_designers: rows.length,
    allocated: rows.filter((row) => row.status === 'working' || row.status === 'on_hold').length,
    available: rows.filter((row) => row.status === 'available').length,
    on_leave: rows.filter((row) => row.status === 'leave').length,
  };

  const pool = Math.max(totals.total_designers, 1);
  const segments = [
    { key: 'open', value: totals.available, color: chartTheme.availability.open },
    { key: 'assigned', value: totals.allocated, color: chartTheme.availability.assigned },
    { key: 'leave', value: totals.on_leave, color: chartTheme.availability.leave },
  ];

  return (
    <Stack spacing={1.75} sx={{ height: '100%', minHeight: 0, py: 0.25 }}>
      <Box sx={{ flexShrink: 0 }}>
        <Box
          sx={{
            display: 'flex',
            height: 10,
            borderRadius: 999,
            overflow: 'hidden',
            bgcolor: chartTheme.surface.track,
            mb: 1.5,
          }}
        >
          {segments.map((segment) => {
            const pct = (segment.value / pool) * 100;
            if (pct <= 0) return null;
            return (
              <Box
                key={segment.key}
                sx={{
                  width: `${pct}%`,
                  bgcolor: segment.color,
                  minWidth: pct > 0 ? 3 : 0,
                }}
              />
            );
          })}
        </Box>
        <Box sx={{ display: 'flex', gap: 2.5 }}>
          {[
            { label: 'Open', value: totals.available, color: chartTheme.availability.open },
            { label: 'Assigned', value: totals.allocated, color: chartTheme.availability.assigned },
            { label: 'Leave', value: totals.on_leave, color: chartTheme.availability.leave },
          ].map((item) => (
            <Box key={item.label}>
              <Typography
                sx={{
                  fontSize: '1.125rem',
                  fontWeight: 700,
                  letterSpacing: '-0.02em',
                  color: item.color,
                  lineHeight: 1.1,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {item.value}
              </Typography>
              <Typography
                sx={{
                  mt: 0.25,
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                  color: chartTheme.ink.tertiary,
                }}
              >
                {item.label}
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {openRows.length === 0 ? (
        <Box
          sx={{
            py: 2.5,
            px: 2,
            textAlign: 'center',
            borderRadius: 2,
            bgcolor: chartTheme.surface.muted,
          }}
        >
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, color: chartTheme.ink.primary }}>
            No open capacity
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: '0.75rem', color: chartTheme.ink.tertiary }}>
            Everyone is assigned or on leave
          </Typography>
        </Box>
      ) : (
        <Stack spacing={0.75} sx={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
          <Typography
            sx={{
              fontSize: '0.65rem',
              fontWeight: 600,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: chartTheme.ink.tertiary,
              flexShrink: 0,
            }}
          >
            Ready now
          </Typography>
          {openRows.map((row) => (
            <Box
              key={row.user_id}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.25,
                py: 0.5,
                flexShrink: 0,
              }}
            >
              <Box
                sx={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  bgcolor: chartTheme.availability.openSoft,
                  color: chartTheme.availability.open,
                  display: 'grid',
                  placeItems: 'center',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                {row.designer_name
                  .split(/\s+/)
                  .filter(Boolean)
                  .slice(0, 2)
                  .map((part) => part[0]?.toUpperCase() ?? '')
                  .join('')}
              </Box>
              <Typography
                sx={{
                  flex: 1,
                  minWidth: 0,
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  color: chartTheme.ink.primary,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
                title={row.designer_name}
              >
                {row.designer_name}
              </Typography>
              <Typography
                sx={{
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  color: chartTheme.availability.open,
                }}
              >
                Open
              </Typography>
            </Box>
          ))}
        </Stack>
      )}
    </Stack>
  );
}
