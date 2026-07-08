import {
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import NotificationsActiveRoundedIcon from '@mui/icons-material/NotificationsActiveRounded';
import { useMutation } from '@tanstack/react-query';
import { sendTimesheetReminder } from '../../api/dashboard';
import type { MissingTimesheetRow } from '../../types';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { formatDate } from '../../utils/format';
import { useToast } from '../../context/ToastContext';

interface MissingTimesheetsWidgetProps {
  rows: MissingTimesheetRow[];
}

export function MissingTimesheetsWidget({ rows }: MissingTimesheetsWidgetProps) {
  const { showSuccess, showError } = useToast();
  const reminderMutation = useMutation({
    mutationFn: sendTimesheetReminder,
    onSuccess: () => showSuccess('Timesheet reminder sent.'),
    onError: (error: Error) => showError(error.message),
  });

  if (!rows.length) {
    return (
      <DashboardPanel title="Missing Timesheets" subtitle="Users without entries for 3+ working days">
        <Typography variant="body2" color="text.secondary">
          All tracked engineers are up to date.
        </Typography>
      </DashboardPanel>
    );
  }

  return (
    <DashboardPanel title="Missing Timesheets" subtitle="3+ consecutive working days without entries" noPadding>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Employee</TableCell>
              <TableCell>Last Entry Date</TableCell>
              <TableCell align="right">Missing Days</TableCell>
              <TableCell align="right">Reminder</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.user_id} hover>
                <TableCell sx={{ fontWeight: 600 }}>{row.employee_name}</TableCell>
                <TableCell>{formatDate(row.last_entry_date ?? undefined) || 'Never'}</TableCell>
                <TableCell align="right">{row.missing_days}</TableCell>
                <TableCell align="right">
                  <Tooltip title="Send reminder">
                    <IconButton
                      size="small"
                      aria-label={`Remind ${row.employee_name}`}
                      disabled={reminderMutation.isPending}
                      onClick={() => reminderMutation.mutate(row.user_id)}
                    >
                      <NotificationsActiveRoundedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </DashboardPanel>
  );
}
