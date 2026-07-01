import {
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
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
            <TableCell>Designer</TableCell>
            <TableCell>Current Milestone</TableCell>
            <TableCell>Due Date</TableCell>
            <TableCell>Execution Status</TableCell>
            <TableCell>Health</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.project_id} hover>
              <TableCell sx={{ fontWeight: 600 }}>{row.tool_number}</TableCell>
              <TableCell>{row.customer_name}</TableCell>
              <TableCell>{row.designer_name ?? '—'}</TableCell>
              <TableCell>{row.current_milestone ?? '—'}</TableCell>
              <TableCell>
                <Typography variant="body2">{formatDate(row.due_date)}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {REASON_LABELS[row.attention_reason]}
                </Typography>
              </TableCell>
              <TableCell>
                <StatusChip status={row.execution_status} />
              </TableCell>
              <TableCell>
                <HealthChip health={row.health} />
              </TableCell>
              <TableCell align="right">
                <Button
                  size="small"
                  endIcon={<OpenInNewIcon />}
                  onClick={() => navigate(`/projects/${row.project_id}`)}
                  sx={{ textTransform: 'none', fontWeight: 600 }}
                >
                  Open
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
