import {
  Box,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import type { ProjectContributorSummary } from '../../../types/TimesheetEntry';
import { formatNumber } from '../../../utils/format';

interface ProjectContributorsPanelProps {
  contributors: ProjectContributorSummary[];
}

export function ProjectContributorsPanel({ contributors }: ProjectContributorsPanelProps) {
  if (!contributors.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No timesheet hours logged yet.
      </Typography>
    );
  }

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {contributors.length} contributor{contributors.length === 1 ? '' : 's'}
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>User</TableCell>
            <TableCell align="right">Hours</TableCell>
            <TableCell align="right">% of Total</TableCell>
            <TableCell>Contribution Reason</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {contributors.map((row) => (
            <TableRow key={row.user_id}>
              <TableCell>
                <Typography variant="body2" sx={{ fontWeight: row.is_project_owner ? 600 : 400 }}>
                  {row.user_name}
                </Typography>
                {row.is_project_owner ? (
                  <Chip size="small" label="Owner" color="primary" sx={{ mt: 0.5 }} />
                ) : null}
              </TableCell>
              <TableCell align="right">{formatNumber(row.total_hours, 1)}</TableCell>
              <TableCell align="right">{formatNumber(row.hours_percent ?? 0, 1)}%</TableCell>
              <TableCell>{row.primary_contribution_label ?? row.role_label}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}
