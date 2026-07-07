import {
  LinearProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import type { DashboardCustomerWorkloadRow } from '../../types';
import { designTokens } from '../../theme/designTokens';
import { formatDisplayValue, formatNumber } from '../../utils/format';
import { prosohmTableContainerSx } from '../../theme/componentStyles';
import { useTheme } from '@mui/material/styles';

interface CustomerWorkloadWidgetProps {
  rows: DashboardCustomerWorkloadRow[];
  compact?: boolean;
  showWorkloadPercent?: boolean;
}

function workloadPercent(row: DashboardCustomerWorkloadRow): number {
  const quoted = Number(row.quoted_hours);
  if (quoted <= 0) return 0;
  return Math.min(100, Math.round((Number(row.actual_hours) / quoted) * 100));
}

export function CustomerWorkloadWidget({
  rows,
  compact = false,
  showWorkloadPercent = false,
}: CustomerWorkloadWidgetProps) {
  const navigate = useNavigate();
  const theme = useTheme();

  if (!rows.length) {
    return (
      <Paper variant="outlined" sx={{ borderRadius: 3, p: 2.5, m: 2.5 }}>
        <Typography variant="body2" color="text.secondary">
          No customer workload data available.
        </Typography>
      </Paper>
    );
  }

  return (
    <TableContainer component={Paper} elevation={0} sx={{ ...prosohmTableContainerSx(theme), border: 'none', boxShadow: 'none' }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            <TableCell>Customer</TableCell>
            <TableCell align="right">Active Tools</TableCell>
            {!compact ? <TableCell align="right">Hours Logged</TableCell> : null}
            {showWorkloadPercent ? <TableCell sx={{ minWidth: 140 }}>Workload</TableCell> : null}
            <TableCell align="right">Designers</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => {
            const percent = workloadPercent(row);
            return (
              <TableRow
                key={row.customer_id}
                hover
                sx={{ cursor: 'pointer' }}
                onClick={() => navigate(`/projects?customer_id=${row.customer_id}`)}
              >
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {formatDisplayValue(row.customer_name)}
                  </Typography>
                </TableCell>
                <TableCell align="right">{formatNumber(row.active_tools, 0)}</TableCell>
                {!compact ? (
                  <TableCell align="right">{formatNumber(row.actual_hours, 1)}</TableCell>
                ) : null}
                {showWorkloadPercent ? (
                  <TableCell>
                    <LinearProgress
                      variant="determinate"
                      value={percent}
                      sx={{
                        height: 8,
                        borderRadius: designTokens.radius.pill,
                        bgcolor: designTokens.semantic.neutralSoft,
                        '& .MuiLinearProgress-bar': {
                          borderRadius: designTokens.radius.pill,
                          bgcolor:
                            percent >= 90
                              ? designTokens.utilization.high
                              : percent >= 75
                                ? designTokens.utilization.medium
                                : designTokens.utilization.low,
                        },
                      }}
                    />
                    <Typography variant="caption" sx={{ fontWeight: 700 }}>
                      {percent}%
                    </Typography>
                  </TableCell>
                ) : null}
                <TableCell align="right">{formatNumber(row.designers_assigned, 0)}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
