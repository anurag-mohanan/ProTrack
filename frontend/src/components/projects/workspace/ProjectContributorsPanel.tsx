import { Chip, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
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
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>Contributor</TableCell>
          <TableCell>Role</TableCell>
          <TableCell align="right">Hours</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {contributors.map((row) => (
          <TableRow key={row.user_id}>
            <TableCell>{row.user_name}</TableCell>
            <TableCell>
              <Chip
                size="small"
                label={row.role_label}
                color={row.is_project_owner ? 'primary' : 'default'}
                variant={row.is_project_owner ? 'filled' : 'outlined'}
              />
            </TableCell>
            <TableCell align="right">{formatNumber(row.total_hours, 1)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
