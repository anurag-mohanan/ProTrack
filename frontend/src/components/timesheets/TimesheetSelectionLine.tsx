import { Box, Typography } from '@mui/material';
import type { Project } from '../../types';
import type { TimesheetToolOption } from './timesheetToolOptions';
import { formatDisplayValue } from '../../utils/format';

interface TimesheetSelectionLineProps {
  selection: TimesheetToolOption | null;
  project: Project | null;
  isBillable: boolean;
}

export function TimesheetSelectionLine({
  selection,
  project,
  isBillable,
}: TimesheetSelectionLineProps) {
  if (!selection) return null;

  if (selection.kind === 'np') {
    const categoryLabel =
      selection.npCategory === 'leave' ? 'Leave' : 'Non-Productive';
    return (
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1, px: 0.5 }}>
        {formatDisplayValue(selection.toolNumber)} • Category: {categoryLabel}
        {' • Billable: '}
        {isBillable ? 'Yes' : 'No'}
      </Typography>
    );
  }

  if (!project) return null;

  const parts = [
    project.tool_number,
    project.part_description,
    project.customer_name,
    project.team_name ? `Team: ${project.team_name}` : null,
    project.design_leader_name ? `Design Leader: ${project.design_leader_name}` : null,
    project.project_type_name,
    isBillable ? 'Billable: Yes' : 'Billable: No',
  ].filter(Boolean);

  return (
    <Box
      sx={{
        mt: 1,
        px: 1,
        py: 0.75,
        borderRadius: 1.5,
        bgcolor: 'action.hover',
        border: 1,
        borderColor: 'divider',
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.25 }}>
        Selected Project
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 500 }}>
        {parts.map((part) => formatDisplayValue(part)).join(' • ')}
      </Typography>
    </Box>
  );
}
