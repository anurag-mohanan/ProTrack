import {
  Box,
  Button,
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
import CheckCircleOutlineOutlinedIcon from '@mui/icons-material/CheckCircleOutlineOutlined';
import { useNavigate } from 'react-router-dom';
import { HealthChip, StatusChip } from '../common/StatusChip';
import type { ProjectAttentionRow } from '../../types';
import { formatCellValue, formatDisplayValue, formatDate } from '../../utils/format';

const MAX_ROWS = 5;

interface ProjectsAttentionTableProps {
  rows: ProjectAttentionRow[];
  filterLabel?: string;
  viewAllHref?: string;
}

export function ProjectsAttentionTable({
  rows,
  filterLabel,
  viewAllHref = '/projects?due=overdue',
}: ProjectsAttentionTableProps) {
  const navigate = useNavigate();
  const visibleRows = rows.slice(0, MAX_ROWS);

  if (!rows.length) {
    const emptyTitle = filterLabel
      ? `No ${filterLabel} right now`
      : 'All projects are on track';
    const emptySubtitle = filterLabel
      ? 'Check back as due dates approach or projects slip.'
      : 'No overdue, blocked, on hold, or due-soon projects require attention right now.';

    return (
      <Paper
        variant="outlined"
        sx={{
          borderRadius: 3,
          p: 3,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          bgcolor: 'success.50',
          borderColor: 'success.light',
        }}
      >
        <CheckCircleOutlineOutlinedIcon color="success" sx={{ fontSize: 28 }} />
        <Box>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'success.dark' }}>
            {emptyTitle}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {emptySubtitle}
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Stack spacing={1.5}>
      <TableContainer
        component={Paper}
        variant="outlined"
        sx={{
          borderRadius: 3,
          boxShadow: (theme) => theme.palette.prosohm.shadowCard,
        }}
      >
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Tool</TableCell>
              <TableCell>Customer</TableCell>
              <TableCell>Current Milestone</TableCell>
              <TableCell>Due Date</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Health</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visibleRows.map((row) => (
              <TableRow
                key={row.project_id}
                hover
                onClick={() => navigate(`/projects/${row.project_id}`)}
                sx={{ cursor: 'pointer' }}
              >
                <TableCell sx={{ fontWeight: 600 }}>{formatDisplayValue(row.tool_number)}</TableCell>
                <TableCell>{formatDisplayValue(row.customer_name)}</TableCell>
                <TableCell>{formatCellValue(row.current_milestone)}</TableCell>
                <TableCell>{formatDate(row.due_date) || '—'}</TableCell>
                <TableCell>
                  <StatusChip status={row.execution_status} />
                </TableCell>
                <TableCell>
                  <HealthChip health={row.health} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          size="small"
          endIcon={<ArrowForwardIcon />}
          onClick={() => navigate(viewAllHref)}
          sx={{ textTransform: 'none', fontWeight: 600 }}
        >
          View All Projects
        </Button>
      </Box>
    </Stack>
  );
}
