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
import { useNavigate } from 'react-router-dom';
import { HealthChip, StatusChip } from '../common/StatusChip';
import type { ProjectAttentionRow } from '../../types';
import { formatDate } from '../../utils/format';

const REASON_LABELS: Record<ProjectAttentionRow['attention_reason'], string> = {
  overdue: 'Overdue',
  blocked: 'Blocked',
  due_soon: 'Due within 7 days',
  on_hold: 'On hold',
};

interface ProjectsAttentionTableProps {
  rows: ProjectAttentionRow[];
}

export function ProjectsAttentionTable({ rows }: ProjectsAttentionTableProps) {
  const navigate = useNavigate();

  if (!rows.length) {
    return (
      <Paper variant="outlined" sx={{ borderRadius: 3, p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          No data available
        </Typography>
      </Paper>
    );
  }

  return (
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
            <TableCell>Tool Number</TableCell>
            <TableCell>Customer</TableCell>
            <TableCell>Current Milestone</TableCell>
            <TableCell>Designer</TableCell>
            <TableCell>Due Date</TableCell>
            <TableCell>Health</TableCell>
            <TableCell>Status</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={row.project_id}
              hover
              sx={{ cursor: 'pointer' }}
              onClick={() => navigate(`/projects/${row.project_id}`)}
            >
              <TableCell sx={{ fontWeight: 600 }}>{row.tool_number}</TableCell>
              <TableCell>{row.customer_name}</TableCell>
              <TableCell>{row.current_milestone ?? '—'}</TableCell>
              <TableCell>{row.designer_name ?? '—'}</TableCell>
              <TableCell>
                <span title={REASON_LABELS[row.attention_reason]}>
                  {formatDate(row.due_date)}
                </span>
              </TableCell>
              <TableCell>
                <HealthChip health={row.health} />
              </TableCell>
              <TableCell>
                <StatusChip status={row.status} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
