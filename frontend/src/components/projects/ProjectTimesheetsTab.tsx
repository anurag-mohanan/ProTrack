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
import { Link } from 'react-router-dom';
import { EmptyState } from '../common/EmptyState';
import type { TimesheetEntry } from '../../types';
import { formatDate, formatNumber } from '../../utils/format';

interface ProjectTimesheetsTabProps {
  entries: TimesheetEntry[];
}

export function ProjectTimesheetsTab({ entries }: ProjectTimesheetsTabProps) {
  if (!entries.length) {
    return (
      <EmptyState
        title="No timesheet entries"
        description="Recent time logged against this project will appear here."
      />
    );
  }

  return (
    <>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Recent entries for this project
      </Typography>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Date</TableCell>
              <TableCell align="right">Hours</TableCell>
              <TableCell>Description</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {entries.map((entry) => (
              <TableRow key={entry.id} hover>
                <TableCell>{formatDate(entry.entry_date)}</TableCell>
                <TableCell align="right">{formatNumber(entry.hours)}</TableCell>
                <TableCell>{entry.description ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <Button component={Link} to="/timesheets" sx={{ mt: 2 }} variant="outlined">
        Manage Timesheets
      </Button>
    </>
  );
}
