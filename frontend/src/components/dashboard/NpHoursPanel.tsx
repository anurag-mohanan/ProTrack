import {
  Box,
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import type { DashboardNpPanel } from '../../types';
import { formatNumber } from '../../utils/format';

interface NpHoursPanelProps {
  panel: DashboardNpPanel | null | undefined;
}

export function NpHoursPanel({ panel }: NpHoursPanelProps) {
  const navigate = useNavigate();

  if (!panel?.codes?.length) {
    return (
      <Paper
        variant="outlined"
        sx={{
          borderRadius: 3,
          p: 2.5,
          height: '100%',
          boxShadow: (theme) => theme.palette.prosohm.shadowCard,
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 650, mb: 1 }}>
          Non-Productive Hours
        </Typography>
        <Typography variant="body2" color="text.secondary">
          No data available
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
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: (theme) => theme.palette.prosohm.shadowCard,
      }}
    >
      <Box sx={{ px: 2.5, pt: 2.5, pb: 1.5 }}>
        <Typography variant="h6" sx={{ fontWeight: 650, letterSpacing: '-0.01em' }}>
          Non-Productive Hours
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Approved NP hours this month
        </Typography>
      </Box>

      <Table size="small" sx={{ flex: 1 }}>
        <TableHead>
          <TableRow>
            <TableCell>Code</TableCell>
            <TableCell>Description</TableCell>
            <TableCell align="right">Hours</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {panel.codes.map((row) => (
            <TableRow key={row.code}>
              <TableCell sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{row.code}</TableCell>
              <TableCell>{row.description}</TableCell>
              <TableCell align="right">{formatNumber(row.hours_this_month)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Box
        sx={{
          px: 2.5,
          py: 2,
          borderTop: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 2,
          flexWrap: 'wrap',
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 650 }}>
          Total NP Hours: {formatNumber(panel.total_np_hours_this_month)}
        </Typography>
        <Button
          variant="outlined"
          size="small"
          onClick={() => navigate('/reports?tab=np-hours')}
          sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
        >
          View NP Report
        </Button>
      </Box>
    </Paper>
  );
}
