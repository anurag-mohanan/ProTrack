import { Box, Chip, Typography, useTheme } from '@mui/material';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import type { TimelineStep } from '../../types/CommandCenter';
import { formatDate } from '../../utils/format';

const STATUS_LABELS: Record<TimelineStep['status'], string> = {
  completed: 'Completed',
  current: 'Current',
  upcoming: 'Upcoming',
  delayed: 'Delayed',
};

const STATUS_COLORS: Record<
  TimelineStep['status'],
  'success' | 'info' | 'default' | 'error'
> = {
  completed: 'success',
  current: 'info',
  upcoming: 'default',
  delayed: 'error',
};

export function WorkflowTimeline({ steps }: { steps: TimelineStep[] }) {
  const theme = useTheme();

  if (!steps.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No milestones configured for this project.
      </Typography>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
      {steps.map((step, index) => (
        <Box key={step.milestone_id ?? `${step.name}-${index}`} sx={{ width: '100%' }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 2,
              px: 2,
              py: 1.5,
              borderRadius: 2,
              border: `1px solid ${theme.palette.divider}`,
              bgcolor:
                step.status === 'current'
                  ? `${theme.palette.info.main}12`
                  : step.status === 'delayed'
                    ? `${theme.palette.error.main}10`
                    : 'background.paper',
            }}
          >
            <Box>
              <Typography sx={{ fontWeight: 600 }}>{step.name}</Typography>
              {step.due_date ? (
                <Typography variant="caption" color="text.secondary">
                  Due {formatDate(step.due_date) || step.due_date}
                </Typography>
              ) : null}
            </Box>
            <Chip
              size="small"
              label={STATUS_LABELS[step.status]}
              color={STATUS_COLORS[step.status]}
            />
          </Box>
          {index < steps.length - 1 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 0.5 }}>
              <ArrowDownwardIcon fontSize="small" color="action" />
            </Box>
          ) : null}
        </Box>
      ))}
    </Box>
  );
}
