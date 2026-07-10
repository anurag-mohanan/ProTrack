import { Box, Chip, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchTimesheetProjectContext } from '../../api/lookups';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { EXECUTION_STATUS_LABELS, PROJECT_STAGE_LABELS } from '../../types/common';
import type { ExecutionStatus, ProjectHealth, ProjectStage } from '../../types/common';
import { formatNumber } from '../../utils/format';
import { HealthBadge } from '../ui/design-system';

interface TimesheetProjectContextPanelProps {
  projectId: string | null;
}

export function TimesheetProjectContextPanel({ projectId }: TimesheetProjectContextPanelProps) {
  const contextQuery = useQuery({
    queryKey: ['timesheet-project-context', projectId],
    queryFn: () => fetchTimesheetProjectContext(projectId!),
    enabled: Boolean(projectId),
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const context = contextQuery.data;
  if (!projectId || !context) return null;

  return (
    <Box
      sx={{
        mt: 1,
        p: 1.25,
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.75 }}>
        Project context
      </Typography>
      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', mb: 1 }}>
        <Chip
          size="small"
          label={`Stage: ${PROJECT_STAGE_LABELS[context.project_stage as ProjectStage] ?? context.project_stage}`}
        />
        <Chip
          size="small"
          label={
            EXECUTION_STATUS_LABELS[context.execution_status as ExecutionStatus] ??
            context.execution_status
          }
          variant="outlined"
        />
        {context.working_model_name ? (
          <Chip size="small" label={context.working_model_name} color="primary" variant="outlined" />
        ) : null}
        <HealthBadge health={context.health as ProjectHealth} />
      </Stack>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 1 }}>
        <Typography variant="body2">
          Quoted: <strong>{formatNumber(context.quoted_hours, 1)}h</strong>
        </Typography>
        <Typography variant="body2">
          Actual: <strong>{formatNumber(context.actual_hours, 1)}h</strong>
        </Typography>
        <Typography variant="body2">
          Remaining: <strong>{formatNumber(context.remaining_hours, 1)}h</strong>
        </Typography>
        <Typography variant="body2">
          Contributors: <strong>{context.contributor_count}</strong>
        </Typography>
      </Stack>
      {context.milestones_due.length ? (
        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
            Milestones due
          </Typography>
          {context.milestones_due.map((milestone) => (
            <Typography key={milestone.id} variant="body2" color="text.secondary">
              {milestone.name}
              {milestone.due_date ? ` · due ${milestone.due_date}` : ''}
            </Typography>
          ))}
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary">
          No open milestones.
        </Typography>
      )}
    </Box>
  );
}
