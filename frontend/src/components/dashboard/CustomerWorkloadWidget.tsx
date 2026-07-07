import {
  Box,
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
import { formatDisplayValue, formatNumber } from '../../utils/format';

interface CustomerWorkloadWidgetProps {
  rows: DashboardCustomerWorkloadRow[];
  compact?: boolean;
}

export function CustomerWorkloadWidget({ rows, compact = false }: CustomerWorkloadWidgetProps) {
  const navigate = useNavigate();

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
            <TableCell>Customer</TableCell>
            <TableCell align="right">Active Tools</TableCell>
            {!compact ? <TableCell align="right">Quoted Hrs</TableCell> : null}
            {!compact ? <TableCell align="right">Actual Hrs</TableCell> : null}
            <TableCell align="right">Designers</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={row.customer_id}
              hover
              sx={{ cursor: 'pointer' }}
              onClick={() => navigate(`/projects?customer_id=${row.customer_id}`)}
            >
              <TableCell>
                <Box>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {formatDisplayValue(row.customer_name)}
                  </Typography>
                  {compact ? null : (
                    <Typography variant="caption" color="text.secondary">
                      {formatNumber(row.active_tools, 0)} tools
                    </Typography>
                  )}
                </Box>
              </TableCell>
              <TableCell align="right">{formatNumber(row.active_tools, 0)}</TableCell>
              {!compact ? (
                <TableCell align="right">{formatNumber(row.quoted_hours, 1)}</TableCell>
              ) : null}
              {!compact ? (
                <TableCell align="right">{formatNumber(row.actual_hours, 1)}</TableCell>
              ) : null}
              <TableCell align="right">{formatNumber(row.designers_assigned, 0)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
