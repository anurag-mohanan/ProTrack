import { Box, Chip, Stack, Typography } from '@mui/material';
import type {
  DashboardDesignerAvailabilityRow,
  DashboardDesignerAvailabilitySummary,
} from '../../types';
import { designTokens } from '../../theme/designTokens';
import { EmptyState } from '../common/EmptyState';

const STATUS_META: Record<
  DashboardDesignerAvailabilityRow['status'],
  { label: string; color: string; soft: string }
> = {
  available: {
    label: 'Open',
    color: designTokens.semantic.success,
    soft: designTokens.semantic.successSoft,
  },
  working: {
    label: 'Assigned',
    color: designTokens.semantic.primary,
    soft: designTokens.semantic.primarySoft,
  },
  on_hold: {
    label: 'On hold',
    color: designTokens.semantic.warning,
    soft: designTokens.semantic.warningSoft,
  },
  leave: {
    label: 'Leave',
    color: designTokens.semantic.neutral,
    soft: designTokens.semantic.neutralSoft,
  },
};

interface ResourceAvailabilityPanelProps {
  summary?: DashboardDesignerAvailabilitySummary;
  rows: DashboardDesignerAvailabilityRow[];
  limit?: number;
}

export function ResourceAvailabilityPanel({
  summary,
  rows,
  limit = 6,
}: ResourceAvailabilityPanelProps) {
  const openRows = rows
    .filter((row) => row.status === 'available')
    .slice(0, limit);

  const totals = summary ?? {
    total_designers: rows.length,
    allocated: rows.filter((row) => row.status === 'working' || row.status === 'on_hold').length,
    available: rows.filter((row) => row.status === 'available').length,
    on_leave: rows.filter((row) => row.status === 'leave').length,
  };

  return (
    <Stack spacing={1.75} sx={{ height: '100%' }}>
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
        <Chip
          size="small"
          label={`${totals.available} open`}
          sx={{
            fontWeight: 700,
            bgcolor: designTokens.semantic.successSoft,
            color: designTokens.semantic.success,
          }}
        />
        <Chip
          size="small"
          label={`${totals.allocated} assigned`}
          sx={{
            fontWeight: 700,
            bgcolor: designTokens.semantic.primarySoft,
            color: designTokens.semantic.primary,
          }}
        />
        <Chip
          size="small"
          label={`${totals.on_leave} leave`}
          sx={{
            fontWeight: 700,
            bgcolor: designTokens.semantic.neutralSoft,
            color: designTokens.semantic.neutral,
          }}
        />
      </Stack>

      {openRows.length === 0 ? (
        <EmptyState
          title="No open capacity"
          description="All designers are assigned, on hold, or on leave."
        />
      ) : (
        <Stack spacing={1.25}>
          {openRows.map((row) => {
            const meta = STATUS_META[row.status];
            return (
              <Box
                key={row.user_id}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1.5,
                  px: 1.25,
                  py: 1,
                  borderRadius: `${designTokens.radius.md}px`,
                  bgcolor: meta.soft,
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Box sx={{ minWidth: 0 }}>
                  <Typography
                    variant="body2"
                    sx={{
                      fontWeight: 700,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={row.designer_name}
                  >
                    {row.designer_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Ready for assignment
                  </Typography>
                </Box>
                <Chip
                  size="small"
                  label={meta.label}
                  sx={{
                    fontWeight: 700,
                    bgcolor: '#fff',
                    color: meta.color,
                    border: '1px solid',
                    borderColor: meta.color,
                  }}
                />
              </Box>
            );
          })}
        </Stack>
      )}
    </Stack>
  );
}
