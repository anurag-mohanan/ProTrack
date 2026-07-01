import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import type { DashboardTeamSummaryRow } from '../../types';
import { formatNumber } from '../../utils/format';

interface TeamSummaryWidgetProps {
  rows: DashboardTeamSummaryRow[];
}

export function TeamSummaryWidget({ rows }: TeamSummaryWidgetProps) {
  if (!rows.length) {
    return (
      <Paper variant="outlined" sx={{ borderRadius: 3, p: 2.5 }}>
        <Typography variant="body2" color="text.secondary">
          No data available.
        </Typography>
      </Paper>
    );
  }

  return (
    <TableContainer
      component={Paper}
      variant="outlined"
      sx={{ borderRadius: 3, boxShadow: (theme) => theme.palette.prosohm.shadowCard }}
    >
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Team</TableCell>
            <TableCell align="right">Projects</TableCell>
            <TableCell align="right">Designers</TableCell>
            <TableCell align="right">Quoted Hrs</TableCell>
            <TableCell align="right">Actual Hrs</TableCell>
            <TableCell align="right">Available Cap.</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.team_id} hover>
              <TableCell sx={{ fontWeight: 600 }}>{row.team_name}</TableCell>
              <TableCell align="right">{formatNumber(row.project_count, 0)}</TableCell>
              <TableCell align="right">{formatNumber(row.designer_count, 0)}</TableCell>
              <TableCell align="right">{formatNumber(row.quoted_hours, 1)}</TableCell>
              <TableCell align="right">{formatNumber(row.actual_hours, 1)}</TableCell>
              <TableCell align="right">
                {formatNumber(row.available_capacity_hours, 1)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
