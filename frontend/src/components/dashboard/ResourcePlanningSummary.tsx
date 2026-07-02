import {
  Box,
  Button,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { useNavigate } from 'react-router-dom';
import type { DashboardTeamSummaryRow } from '../../types';
import { formatNumber } from '../../utils/format';

interface ResourcePlanningSummaryProps {
  rows: DashboardTeamSummaryRow[];
}

function utilizationPercent(row: DashboardTeamSummaryRow): number {
  const capacity = Number(row.actual_hours) + Number(row.available_capacity_hours);
  if (capacity <= 0) return 0;
  return Math.min(100, Math.round((Number(row.actual_hours) / capacity) * 100));
}

export function ResourcePlanningSummary({ rows }: ResourcePlanningSummaryProps) {
  const navigate = useNavigate();

  if (!rows.length) {
    return (
      <Paper variant="outlined" sx={{ borderRadius: 3, p: 2.5 }}>
        <Typography variant="body2" color="text.secondary">
          No team capacity data available.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: 3,
        overflow: 'hidden',
        boxShadow: (theme) => theme.palette.prosohm.shadowCard,
      }}
    >
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Team</TableCell>
              <TableCell align="right">Designers</TableCell>
              <TableCell align="right">Active Projects</TableCell>
              <TableCell align="right">Available Capacity (Hrs)</TableCell>
              <TableCell sx={{ minWidth: 180 }}>Utilization</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.slice(0, 5).map((row) => {
              const utilization = utilizationPercent(row);
              return (
                <TableRow key={row.team_id} hover>
                  <TableCell sx={{ fontWeight: 600 }}>{row.team_name}</TableCell>
                  <TableCell align="right">{formatNumber(row.designer_count, 0)}</TableCell>
                  <TableCell align="right">{formatNumber(row.project_count, 0)}</TableCell>
                  <TableCell align="right">{formatNumber(row.available_capacity_hours, 1)}</TableCell>
                  <TableCell>
                    <Stack spacing={0.75}>
                      <Typography variant="caption" sx={{ fontWeight: 600 }}>
                        {utilization}%
                      </Typography>
                      <LinearProgress
                        variant="determinate"
                        value={utilization}
                        sx={{
                          height: 6,
                          borderRadius: 999,
                          bgcolor: 'grey.100',
                          '& .MuiLinearProgress-bar': {
                            borderRadius: 999,
                            bgcolor:
                              utilization >= 90
                                ? 'error.main'
                                : utilization >= 75
                                  ? 'warning.main'
                                  : 'success.main',
                          },
                        }}
                      />
                    </Stack>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', p: 1.5, borderTop: 1, borderColor: 'divider' }}>
        <Button
          size="small"
          endIcon={<ArrowForwardIcon />}
          onClick={() => navigate('/resource-planning')}
          sx={{ textTransform: 'none', fontWeight: 600 }}
        >
          View Resource Planning
        </Button>
      </Box>
    </Paper>
  );
}
