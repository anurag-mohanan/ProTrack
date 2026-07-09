import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import type { NavigateFunction } from 'react-router-dom';
import type { StaffProjectRow } from '../../types';
import { navigateWithBack } from '../../hooks/useBackNavigation';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { formatDate, formatNumber } from '../../utils/format';
import { HealthBadge, ProjectStageBadge } from '../ui/design-system';

interface MyProjectsWidgetProps {
  rows: StaffProjectRow[];
  navigate: NavigateFunction;
}

export function MyProjectsWidget({ rows, navigate }: MyProjectsWidgetProps) {
  if (!rows.length) {
    return (
      <DashboardPanel title="My Projects" subtitle="Assigned active tools">
        <Typography variant="body2" color="text.secondary">
          No active projects are assigned to you right now.
        </Typography>
      </DashboardPanel>
    );
  }

  return (
    <DashboardPanel title="My Projects" subtitle="Your assigned active tools" noPadding>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Tool Number</TableCell>
              <TableCell>Customer</TableCell>
              <TableCell>Current Stage</TableCell>
              <TableCell>Due Date</TableCell>
              <TableCell align="right">Progress</TableCell>
              <TableCell>Hours Used</TableCell>
              <TableCell>Health</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow
                key={row.project_id}
                hover
                sx={{ cursor: 'pointer' }}
                onClick={() => navigateWithBack(navigate, `/projects/${row.project_id}`)}
              >
                <TableCell sx={{ fontWeight: 700 }}>{row.tool_number}</TableCell>
                <TableCell>{row.customer_name}</TableCell>
                <TableCell>
                  <ProjectStageBadge stage={row.current_stage as never} />
                </TableCell>
                <TableCell>{formatDate(row.due_date ?? undefined) || '—'}</TableCell>
                <TableCell align="right">{formatNumber(row.progress_percent, 0)}%</TableCell>
                <TableCell align="right">{formatNumber(row.hours_logged, 1)}</TableCell>
                <TableCell>
                  {row.health ? <HealthBadge health={row.health as never} /> : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </DashboardPanel>
  );
}
