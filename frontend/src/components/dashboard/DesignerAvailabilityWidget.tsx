import { Box, Chip, Grid, Paper, Stack, Typography } from '@mui/material';
import type {
  DashboardDesignerAvailabilityRow,
  DashboardDesignerAvailabilitySummary,
  DesignerAvailabilityStatus,
} from '../../types';
import { PROJECT_STAGE_LABELS } from '../../types/common';
import { formatDisplayValue } from '../../utils/format';

const STATUS_CONFIG: Record<
  DesignerAvailabilityStatus,
  { label: string; color: 'success' | 'info' | 'warning' | 'default' }
> = {
  available: { label: 'Available', color: 'success' },
  working: { label: 'Working', color: 'info' },
  on_hold: { label: 'On Hold', color: 'warning' },
  leave: { label: 'Leave', color: 'default' },
};

interface DesignerAvailabilityWidgetProps {
  summary: DashboardDesignerAvailabilitySummary;
  designers: DashboardDesignerAvailabilityRow[];
}

function SummaryStat({ label, value }: { label: string; value: number }) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        borderRadius: 2.5,
        textAlign: 'center',
        bgcolor: 'grey.50',
      }}
    >
      <Typography variant="h5" sx={{ fontWeight: 700 }}>
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Paper>
  );
}

export function DesignerAvailabilityWidget({
  summary,
  designers,
}: DesignerAvailabilityWidgetProps) {
  if (!designers.length) {
    return (
      <Paper variant="outlined" sx={{ borderRadius: 3, p: 2.5 }}>
        <Typography variant="body2" color="text.secondary">
          No data available.
        </Typography>
      </Paper>
    );
  }

  return (
    <Stack spacing={2.5}>
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 6, sm: 3 }}>
          <SummaryStat label="Total Designers" value={summary.total_designers} />
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <SummaryStat label="Allocated" value={summary.allocated} />
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <SummaryStat label="Available" value={summary.available} />
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <SummaryStat label="On Leave" value={summary.on_leave} />
        </Grid>
      </Grid>

      <Stack spacing={1}>
        {designers.map((designer) => {
          const config = STATUS_CONFIG[designer.status];
          return (
            <Paper
              key={designer.user_id}
              variant="outlined"
              sx={{
                p: 2,
                borderRadius: 2.5,
                borderLeft: '4px solid',
                borderLeftColor:
                  designer.status === 'available'
                    ? 'success.main'
                    : designer.status === 'working'
                      ? 'info.main'
                      : designer.status === 'on_hold'
                        ? 'warning.main'
                        : 'grey.400',
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: 2,
                  flexWrap: 'wrap',
                }}
              >
                <Box>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    {formatDisplayValue(designer.designer_name)}
                  </Typography>
                  {designer.current_tool_number ? (
                    <Typography variant="body2" color="text.secondary">
                      {formatDisplayValue(designer.current_tool_number)}
                      {designer.current_customer_name
                        ? ` · ${formatDisplayValue(designer.current_customer_name)}`
                        : ''}
                    </Typography>
                  ) : null}
                  {designer.current_stage || designer.current_milestone ? (
                    <Typography variant="caption" color="text.secondary">
                      {[
                        designer.current_stage ? PROJECT_STAGE_LABELS[designer.current_stage] : null,
                        formatDisplayValue(designer.current_milestone) !== '—'
                          ? formatDisplayValue(designer.current_milestone)
                          : null,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </Typography>
                  ) : null}
                </Box>
                <Chip label={config.label} color={config.color} size="small" />
              </Box>
            </Paper>
          );
        })}
      </Stack>
    </Stack>
  );
}
