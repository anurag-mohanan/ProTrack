import { Box, Grid, Typography } from '@mui/material';
import type { Project } from '../../types';
import type { TimesheetToolOption } from './timesheetToolOptions';
import { formatDisplayValue } from '../../utils/format';

interface TimesheetProjectInfoPanelProps {
  selection: TimesheetToolOption | null;
  project: Project | null;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <Grid size={{ xs: 12, sm: 6 }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {formatDisplayValue(value) || '—'}
      </Typography>
    </Grid>
  );
}

export function TimesheetProjectInfoPanel({
  selection,
  project,
}: TimesheetProjectInfoPanelProps) {
  if (!selection) {
    return (
      <Box
        sx={{
          p: 2,
          borderRadius: 2,
          border: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
          Project Information
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Select a tool number to view customer, team, and project details.
        </Typography>
      </Box>
    );
  }

  if (selection.kind === 'np') {
    return (
      <Box
        sx={{
          p: 2,
          borderRadius: 2,
          border: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
          Non-Productive Entry
        </Typography>
        <InfoRow label="NP Code" value={selection.toolNumber} />
        <InfoRow label="Activity" value={selection.label.split('—').slice(1).join('—').trim() || selection.label} />
      </Box>
    );
  }

  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
        Project Information
      </Typography>
      <Grid container spacing={1.5}>
        <InfoRow label="Customer" value={project?.customer_name ?? ''} />
        <InfoRow label="Project" value={project?.tool_number ?? selection.toolNumber} />
        <InfoRow label="Team" value={project?.team_name ?? ''} />
        <InfoRow label="Design Leader" value={project?.design_leader_name ?? ''} />
        <InfoRow label="Project Type" value={project?.project_type_name ?? ''} />
      </Grid>
    </Box>
  );
}
