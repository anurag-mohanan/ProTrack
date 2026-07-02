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
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import { useNavigate } from 'react-router-dom';
import type { DashboardTeamSummaryRow } from '../../types';
import { formatCellValue, formatNumber } from '../../utils/format';

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
      <Paper
        variant="outlined"
        sx={{
          borderRadius: 2.5,
          p: 3,
          boxShadow: (theme) => theme.palette.prosohm.shadowCard,
        }}
      >
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
        borderRadius: 2.5,
        overflow: 'hidden',
        boxShadow: (theme) => theme.palette.prosohm.shadowCard,
      }}
    >
      <Box
        sx={{
          px: 2.5,
          py: 1.75,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <GroupsOutlinedIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Team Capacity Overview
        </Typography>
      </Box>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 700, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Team
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Designers
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Projects
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Capacity
              </TableCell>
              <TableCell sx={{ minWidth: 200, fontWeight: 700, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Utilization
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.slice(0, 5).map((row) => {
              const utilization = utilizationPercent(row);
              return (
                <TableRow
                  key={row.team_id}
                  hover
                  sx={{
                    '& td': { py: 1.25, height: 48 },
                    transition: 'background-color 0.2s ease',
                  }}
                >
                  <TableCell sx={{ fontWeight: 600 }}>
                    {formatCellValue(row.team_name) || '—'}
                  </TableCell>
                  <TableCell align="right">{formatNumber(row.designer_count, 0)}</TableCell>
                  <TableCell align="right">{formatNumber(row.project_count, 0)}</TableCell>
                  <TableCell align="right">
                    {formatNumber(row.available_capacity_hours, 1)} hrs
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                      <LinearProgress
                        variant="determinate"
                        value={utilization}
                        sx={{
                          flex: 1,
                          height: 8,
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
                      <Typography
                        variant="caption"
                        sx={{ fontWeight: 700, minWidth: 36, textAlign: 'right' }}
                      >
                        {utilization}%
                      </Typography>
                    </Stack>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          px: 2,
          py: 1.5,
          borderTop: 1,
          borderColor: 'divider',
          bgcolor: 'background.default',
        }}
      >
        <Button
          size="small"
          endIcon={<ArrowForwardIcon />}
          onClick={() => navigate('/resource-planning')}
          sx={{ textTransform: 'none', fontWeight: 600, borderRadius: 2 }}
        >
          View Resource Planning →
        </Button>
      </Box>
    </Paper>
  );
}
