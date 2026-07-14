import {
  Box,
  Stack,
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
  /** Narrow right-rail layout (no wide table). */
  compact?: boolean;
}

export function MyProjectsWidget({ rows, navigate, compact = false }: MyProjectsWidgetProps) {
  if (!rows.length) {
    return (
      <DashboardPanel title="My Projects" subtitle="Assigned active tools">
        <Typography variant="body2" color="text.secondary">
          No active projects are assigned to you right now.
        </Typography>
      </DashboardPanel>
    );
  }

  if (compact) {
    return (
      <DashboardPanel title="My Projects" subtitle="Assigned active tools" noPadding>
        <Stack component="ul" sx={{ m: 0, p: 0, listStyle: 'none' }}>
          {rows.slice(0, 8).map((row) => (
            <Box
              component="li"
              key={row.project_id}
              onClick={() => navigateWithBack(navigate, `/projects/${row.project_id}`)}
              sx={{
                px: 1.5,
                py: 1,
                borderBottom: '1px solid',
                borderColor: 'divider',
                cursor: 'pointer',
                '&:last-of-type': { borderBottom: 'none' },
                '&:hover': { bgcolor: 'action.hover' },
              }}
            >
              <Stack
                direction="row"
                spacing={0.75}
                sx={{ alignItems: 'center', justifyContent: 'space-between' }}
              >
                <Typography sx={{ fontWeight: 800, fontSize: '0.85rem' }} noWrap>
                  {row.tool_number}
                </Typography>
                {row.health ? <HealthBadge health={row.health as never} /> : null}
              </Stack>
              <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
                {row.customer_name || '—'}
              </Typography>
              <Stack direction="row" spacing={1} sx={{ mt: 0.35, alignItems: 'center', flexWrap: 'wrap' }}>
                <ProjectStageBadge stage={row.current_stage as never} />
                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
                  {formatNumber(row.progress_percent, 0)}% ·{' '}
                  {formatDate(row.due_date ?? undefined) || '—'}
                </Typography>
              </Stack>
            </Box>
          ))}
        </Stack>
        {rows.length > 8 ? (
          <Typography
            variant="caption"
            color="primary"
            sx={{ display: 'block', px: 1.5, py: 1, cursor: 'pointer', fontWeight: 700 }}
            onClick={() => navigateWithBack(navigate, '/projects')}
          >
            View all {rows.length} projects
          </Typography>
        ) : null}
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
